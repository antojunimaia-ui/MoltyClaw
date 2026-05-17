import os
import sys
import asyncio
import json
import logging
import re
import queue
import threading
from typing import Optional, List, Dict, Any

import traceback
from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, HTTPException, Body, Query, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
from starlette.middleware.cors import CORSMiddleware

# Configuração de Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

from moltyclaw import MoltyClaw
import skills
from scheduler import SchedulerManager
from rich.console import Console
from dotenv import load_dotenv
from initializer import MOLTY_DIR

console = Console()
load_dotenv(os.path.join(MOLTY_DIR, '.env'))

# --- Config & Security ---
GATEWAY_TOKEN = None

def load_molty_config():
    """Lê moltyclaw.json removendo comentários para compatibilidade com OpenClaw."""
    config_path = os.path.join(MOLTY_DIR, "moltyclaw.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Remove comentários // e /* */
            content = re.sub(r'//.*?\n|/\*.*?\*/', '', content, flags=re.S)
            return json.loads(content)
    except Exception as e:
        console.print(f"[bold red]Erro ao carregar moltyclaw.json:[/bold red] {e}")
        return {}

def verify_token(request: Request):
    """Verifica se o token enviado bate com o configurado em moltyclaw.json."""
    if not GATEWAY_TOKEN:
        return True # Se não houver token configurado, libera (dev mode)
    
    # Check Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        if token == GATEWAY_TOKEN:
            return True
            
    # Check Query Param (para WebSockets ou links diretos)
    query_token = request.query_params.get("token")
    if query_token == GATEWAY_TOKEN:
        return True
        
    raise HTTPException(status_code=401, detail="Não autorizado: Token do Gateway inválido ou ausente.")

# Estado Global
master_agent: Optional[MoltyClaw] = None
scheduler: Optional[SchedulerManager] = None
agent_instances = {}
ready = False
active_processes = {}
active_websockets: List[WebSocket] = []

# --- App Initialization ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global master_agent, scheduler, ready
    # Carrega configurações do JSON (OpenClaw Parity)
    config = load_molty_config()
    global GATEWAY_TOKEN
    GATEWAY_TOKEN = config.get("gateway", {}).get("auth", {}).get("token") or os.environ.get("GATEWAY_TOKEN")
    
    if GATEWAY_TOKEN:
        console.print(f"[bold yellow]🔒 Segurança Ativa: Token do Gateway carregado de moltyclaw.json[/bold yellow]")
    else:
        console.print("[bold red]⚠️  Aviso: Nenhum GATEWAY_TOKEN encontrado. O painel está desprotegido![/bold red]")

    # Inicializa o Agente Mestre
    master_agent = MoltyClaw(name="MoltyClaw (WebUI Gateway Hub)")
    
    # Inicia o Scheduler
    scheduler = SchedulerManager(master_agent)
    asyncio.create_task(scheduler.run())
    
    # Inicia Browser
    await master_agent.init_browser()
    
    # Conecta MCP se houver
    if master_agent.mcp_hub:
        await master_agent.mcp_hub.connect_servers()
        
    ready = True
    console.print("[bold green]✅ Gateway Online e Pronto para Conexões![/bold green]")
    
    # Auto-start de integrações já configuradas no .env
    auto_start_configured_integrations()
    
    # Inicia Monitor de Processos
    asyncio.create_task(integration_monitor())
    
    yield
    # Cleanup (if needed)

app = FastAPI(title="MoltyClaw Gateway", lifespan=lifespan)

# CORS para permitir acesso de diferentes origens se necessário
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos e templates
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)



async def integration_monitor():
    """Monitora se processos de integração morreram e avisa o front via WS."""
    last_status = {}
    while True:
        await asyncio.sleep(5)
        current_status = await get_integrations()
        if current_status != last_status:
            last_status = current_status
            await broadcast_status()

# --- Dependências ---

def get_or_create_agent(agent_id="MoltyClaw"):
    global master_agent
    if agent_id == "MoltyClaw":
        return master_agent
    
    if agent_id not in agent_instances:
        console.print(f"[info]🆕 Criando instância para sub-agente: {agent_id}[/info]")
        agents_dir = os.path.join(MOLTY_DIR, "agents", agent_id)
        name = agent_id
        if os.path.exists(os.path.join(agents_dir, "config.json")):
            try:
                with open(os.path.join(agents_dir, "config.json"), "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    name = cfg.get("name", agent_id)
            except: pass
        
        # O sub-agente compartilha o loop e o browser
        new_agent = MoltyClaw(name=name, agent_id=agent_id)
        # Nota: init_browser é rápido se o browser já estiver aberto no master
        asyncio.create_task(new_agent.init_browser())
        agent_instances[agent_id] = new_agent
        
    return agent_instances[agent_id]

# --- WebSockets ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    # Validação de Segurança para WebSocket
    if GATEWAY_TOKEN and token != GATEWAY_TOKEN:
        await websocket.close(code=4001) # Unauthorized
        return

    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Envia status inicial
        status = await get_integrations()
        await websocket.send_json({"type": "integrations_status", "data": status})
        
        while True:
            # Mantém a conexão aberta e responde a pings se necessário
            data = await websocket.receive_text()
            # Se o cliente enviar algo, podemos processar aqui
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

async def broadcast_status():
    if not active_websockets: return
    status = await get_integrations()
    dead_sockets = []
    for ws in active_websockets:
        try:
            await ws.send_json({"type": "integrations_status", "data": status})
        except:
            dead_sockets.append(ws)
    for ws in dead_sockets:
        if ws in active_websockets:
            active_websockets.remove(ws)

# --- Rotas Web ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    return {"ready": ready}

@app.get("/temp/{filename}")
async def serve_temp(filename: str):
    path = os.path.abspath(os.path.join(MOLTY_DIR, "temp", filename))
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Arquivo não encontrado")

# --- Chat API ---

class ChatRequest(BaseModel):
    message: str
    agent_id: str = "MoltyClaw"

@app.post("/api/chat")
async def chat(
    request: Request,
    message: Optional[str] = Body(None),
    agent_id: Optional[str] = Body("MoltyClaw"),
    file: Optional[UploadFile] = File(None),
    authorized: bool = Depends(verify_token)
):
    if not ready:
        raise HTTPException(status_code=503, detail="Gateway está iniciando o Browser...")

    # Se for JSON ou Form (suporte híbrido para script.js antigo)
    if not message:
        try:
            form_data = await request.form()
            message = form_data.get("message")
            agent_id = form_data.get("agent_id", "MoltyClaw")
        except:
            # Tentar pegar do corpo JSON se não for form
            try:
                data = await request.json()
                message = data.get("message")
                agent_id = data.get("agent_id", "MoltyClaw")
            except: pass

    if not message:
        raise HTTPException(status_code=400, detail="Mensagem vazia")

    target_agent = get_or_create_agent(agent_id)
    if not target_agent:
        raise HTTPException(500, "Falha ao obter ou criar agente")
    
    # Processar arquivo se houver
    if file and file.filename:
        os.makedirs(os.path.join(MOLTY_DIR, "temp"), exist_ok=True)
        filepath = os.path.join(MOLTY_DIR, "temp", f"webui_{file.filename}")
        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)
        
        message += f"\n\n[SISTEMA: O usuário enviou o arquivo: {os.path.abspath(filepath)}]"
        
        # Audio check
        ext = file.filename.split(".")[-1].lower()
        if ext in ['mp3', 'ogg', 'wav', 'm4a']:
            text = await target_agent.transcribe_audio(filepath)
            if text:
                message += f"\n(Áudio Transcrito): '{text}'"

    # Streaming Response (SSE)
    async def event_generator():
        q = asyncio.Queue()

        async def stream_cb(token: str):
            await q.put({"type": "token", "content": token})

        async def tool_cb(msg: str):
            await q.put({"type": "tool", "content": msg})

        # Task de processamento
        async def process():
            try:
                res = await target_agent.ask(
                    prompt=message,
                    silent=False,
                    stream_callback=stream_cb,
                    tool_callback=tool_cb
                )
                if res and isinstance(res, str) and "[AUDIO_REPLY:" in res:
                    match = re.search(r'\[AUDIO_REPLY:\s*([^\]]+)\]', res)
                    if match:
                        fname = os.path.basename(match.group(1).strip())
                        await q.put({"type": "token", "content": f"\n\n[AUDIO_REPLY: {fname}]\n\n"})
                
                await q.put({"type": "done"})
            except Exception as e:
                console.print(f"[bold red]Erro no Chat:[/bold red] {traceback.format_exc()}")
                await q.put({"type": "error", "content": str(e)})

        asyncio.create_task(process())

        while True:
            evt = await q.get()
            yield f"data: {json.dumps(evt)}\n\n"
            if evt["type"] in ["done", "error"]:
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- Integrations API ---

@app.get("/api/integrations")
async def get_integrations():
    status = {}
    for key, procs in active_processes.items():
        if any(p.poll() is None for p in procs):
            parts = key.split("_")
            int_name = parts[0]
            agent_id = "_".join(parts[1:])
            if int_name not in status: status[int_name] = []
            status[int_name].append(agent_id)
    return status

@app.get("/api/integrations/{platform}/config")
async def get_integration_config(platform: str):
    """Retorna a configuração atual de uma integração (com tokens mascarados)"""
    import sys
    sys.path.append(os.path.join(BASE_DIR, "webui"))
    from .env_manager import EnvManager
    
    env_mgr = EnvManager()
    config = env_mgr.get_integration_config(platform)
    return config

@app.post("/api/integrations/{platform}/config")
async def save_integration_config(platform: str, data: Dict[str, Any]):
    """Salva a configuração de uma integração no .env e já ativa automaticamente"""
    import sys
    sys.path.append(os.path.join(BASE_DIR, "webui"))
    from .env_manager import EnvManager
    from dotenv import load_dotenv
    
    fields = data.get("fields", {})
    
    if not fields:
        raise HTTPException(400, "Nenhum campo fornecido")
    
    env_mgr = EnvManager()
    success = env_mgr.save_integration_config(platform, fields)
    
    if not success:
        raise HTTPException(500, "Falha ao salvar configuração")

    # Recarrega as variáveis de ambiente para que _is_configured() enxergue os novos valores
    load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)

    # Auto-start: se agora está configurado, sobe a integração imediatamente
    auto_started = False
    if _is_configured(platform):
        # Para a instância antiga se existir (pode ter credenciais velhas)
        _stop_integration(platform)
        auto_started = _start_integration(platform)
        asyncio.create_task(broadcast_status())
        console.print(f"[bold green]🚀 Auto-start após config:[/bold green] {platform} iniciado.")

    return {
        "success": True,
        "message": f"Configuração de {platform} salva com sucesso!",
        "auto_started": auto_started
    }

@app.post("/api/integrations/{platform}/test")
async def test_integration_connection(platform: str, data: Dict[str, Any]):
    """Testa a conexão com uma integração antes de salvar"""
    fields = data.get("fields", {})
    
    if not fields:
        raise HTTPException(400, "Nenhum campo fornecido")
    
    # Testa a conexão baseado na plataforma
    try:
        if platform == "discord":
            token = fields.get("DISCORD_TOKEN")
            if not token:
                raise HTTPException(400, "Token do Discord é obrigatório")
            
            # Testa o token fazendo uma requisição à API do Discord
            import aiohttp
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bot {token}"}
                async with session.get("https://discord.com/api/v10/users/@me", headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        bot_data = await resp.json()
                        return {
                            "success": True, 
                            "message": f"✅ Conectado como {bot_data.get('username')}#{bot_data.get('discriminator')}"
                        }
                    elif resp.status == 401:
                        raise HTTPException(400, "Token inválido ou expirado")
                    else:
                        raise HTTPException(400, f"Erro na API do Discord: {resp.status}")
                
        elif platform == "telegram":
            token = fields.get("TELEGRAM_TOKEN")
            if not token:
                raise HTTPException(400, "Token do Telegram é obrigatório")
            
            # Testa o token
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.telegram.org/bot{token}/getMe", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok"):
                            bot_data = data.get("result", {})
                            return {
                                "success": True,
                                "message": f"✅ Conectado como @{bot_data.get('username')}"
                            }
                        else:
                            raise HTTPException(400, "Token inválido")
                    else:
                        raise HTTPException(400, f"Erro na API do Telegram: {resp.status}")
                
        elif platform == "twitter":
            # Twitter requer 4 tokens, teste básico de formato
            required = ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"]
            for field in required:
                if not fields.get(field):
                    raise HTTPException(400, f"{field} é obrigatório")
            
            # Teste básico (não faz requisição real para economizar rate limit)
            return {
                "success": True,
                "message": "✅ Credenciais do Twitter parecem válidas (formato OK)"
            }
            
        elif platform == "bluesky":
            handle = fields.get("BLUESKY_HANDLE", "").lstrip("@")
            password = fields.get("BLUESKY_APP_PASSWORD")
            
            if not handle or not password:
                raise HTTPException(400, "Handle e App Password são obrigatórios")
            
            # Testa login
            try:
                from atproto import Client
                client = Client()
                await asyncio.to_thread(client.login, handle, password)
                return {
                    "success": True,
                    "message": f"✅ Conectado como @{handle}"
                }
            except Exception as e:
                raise HTTPException(400, f"Falha no login: {str(e)}")
                
        elif platform == "whatsapp":
            # WhatsApp não tem teste de token (usa QR Code)
            return {
                "success": True,
                "message": "✅ Configuração salva. Escaneie o QR Code ao iniciar."
            }
            
        else:
            raise HTTPException(400, "Plataforma não suportada")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao testar conexão: {str(e)}")

class IntegrationToggleRequest(BaseModel):
    name: str
    agent_id: str = "MoltyClaw"


# ── Mapa de comandos por integração ──────────────────────────────────────────

def _get_cmd_map():
    return {
        "whatsapp": [
            f'"{sys.executable}" "{os.path.join(BASE_DIR, "integrations", "whatsapp_server.py")}"',
            f'node "{os.path.join(BASE_DIR, "integrations", "whatsapp_bridge.js")}"'
        ],
        "discord":  [f'"{sys.executable}" "{os.path.join(BASE_DIR, "integrations", "discord_bot.py")}"'],
        "telegram": [f'"{sys.executable}" "{os.path.join(BASE_DIR, "integrations", "telegram_bot.py")}"'],
        "twitter":  [f'"{sys.executable}" "{os.path.join(BASE_DIR, "integrations", "twitter_bot.py")}"'],
        "bluesky":  [f'"{sys.executable}" "{os.path.join(BASE_DIR, "integrations", "bluesky_bot.py")}"'],
    }


def _is_configured(platform: str) -> bool:
    """Verifica se uma integração tem as credenciais mínimas no .env"""
    required = {
        "discord":  ["DISCORD_TOKEN"],
        "telegram": ["TELEGRAM_TOKEN"],
        "whatsapp": [],                  # WhatsApp não precisa de token, usa QR Code
        "twitter":  ["TWITTER_API_KEY", "TWITTER_API_SECRET",
                     "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET"],
        "bluesky":  ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"],
    }
    for key in required.get(platform, []):
        if not os.getenv(key):
            return False
    return True


def _start_integration(name: str, agent_id: str = "MoltyClaw") -> bool:
    """Inicia os processos de uma integração. Retorna True se iniciou."""
    import subprocess

    cmd_map = _get_cmd_map()
    if name not in cmd_map:
        return False

    # Evita duplicata
    key = f"{name}_{agent_id}"
    if key in active_processes and any(p.poll() is None for p in active_processes[key]):
        return True  # já está rodando

    env = os.environ.copy()
    env[f"MOLTY_{name.upper()}_ACTIVE"] = "1"

    if agent_id != "MoltyClaw":
        agent_env = os.path.join(MOLTY_DIR, "agents", agent_id, ".env")
        if os.path.exists(agent_env):
            from dotenv import dotenv_values
            env.update(dotenv_values(agent_env))

    procs = []
    for base_cmd in cmd_map[name]:
        cmd = base_cmd
        if sys.executable in cmd:
            cmd += f' --agent "{agent_id}"'
        p = subprocess.Popen(cmd, shell=True, env=env)
        procs.append(p)

    active_processes[key] = procs
    return True


def _stop_integration(name: str, agent_id: str = "MoltyClaw") -> bool:
    """Para os processos de uma integração."""
    key = f"{name}_{agent_id}"
    if key in active_processes:
        for p in active_processes[key]:
            try:
                p.terminate()
            except Exception:
                pass
        active_processes.pop(key, None)
        return True
    return False


def auto_start_configured_integrations():
    """
    Chamado na inicialização do gateway.
    Sobe automaticamente todas as integrações que já têm credenciais no .env.
    Usa um pequeno delay para garantir que o browser do Gateway já está estável.
    """
    import threading

    def _delayed_start():
        import time
        # Aguarda 5s para o browser do Gateway estabilizar na porta 9222
        time.sleep(5)

        platforms = ["discord", "telegram", "whatsapp", "twitter", "bluesky"]
        started = []
        for platform in platforms:
            if _is_configured(platform):
                # Stagger de 1.5s entre cada bot para evitar race condition no lock 9223
                if started:
                    time.sleep(1.5)
                if _start_integration(platform):
                    started.append(platform)
                    console.print(f"[bold green]🚀 Auto-start:[/bold green] {platform} iniciado automaticamente.")

        if not started:
            console.print("[dim]ℹ️  Nenhuma integração configurada para auto-start.[/dim]")

    # Roda em thread separada para não bloquear o lifespan do FastAPI
    threading.Thread(target=_delayed_start, daemon=True).start()


@app.post("/api/integrations/{action}")
async def toggle_integration(action: str, data: IntegrationToggleRequest, authorized: bool = Depends(verify_token)):
    name = data.name
    agent_id = data.agent_id

    if action == "start":
        if name not in _get_cmd_map():
            return {"error": "Integração desconhecida"}
        ok = _start_integration(name, agent_id)
        if ok:
            asyncio.create_task(broadcast_status())
            return {"success": True}
        return {"error": "Falha ao iniciar integração"}

    elif action == "stop":
        ok = _stop_integration(name, agent_id)
        asyncio.create_task(broadcast_status())
        return {"success": True} if ok else {"error": "Não encontrada ou já parada"}

    return {"error": "Ação inválida"}

# --- Agents & Files API ---

@app.get("/api/agents")
async def list_agents():
    agents_dir = os.path.join(MOLTY_DIR, "agents")
    os.makedirs(agents_dir, exist_ok=True)
    
    agent_list = [{
        "id": "MoltyClaw", "name": "MoltyClaw", 
        "description": "Agente Mestre Orquestrador.",
        "provider": "Kernel Central", "tools_mcp": ["Todos"], "tools_local": ["Todas"], "is_master": True
    }]
    
    for agent_id in os.listdir(agents_dir):
        p = os.path.join(agents_dir, agent_id, "config.json")
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                cfg["id"] = agent_id
                cfg["is_master"] = False
                agent_list.append(cfg)
            except: pass
    return {"agents": agent_list}

@app.post("/api/agents")
async def save_agent(data: Dict[str, Any]):
    agent_id = data.get("id") or data.get("name", "").replace(" ", "_").lower()
    if not agent_id or agent_id.lower() == "moltyclaw":
        raise HTTPException(400, "Nome reservado ou inválido")
        
    agents_dir = os.path.join(MOLTY_DIR, "agents", agent_id)
    os.makedirs(agents_dir, exist_ok=True)
    
    config = {
        "name": data.get("name", agent_id),
        "description": data.get("description", "Agente Especializado."),
        "provider": data.get("provider", "mistral"),
        "tools_mcp": data.get("tools_mcp", []),
        "tools_local": data.get("tools_local", ["DDG_SEARCH", "READ_PAGE"])
    }
    
    with open(os.path.join(agents_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
        
    # Salvar .env
    env_vars = data.get("env_vars", {})
    with open(os.path.join(agents_dir, ".env"), "w", encoding="utf-8") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
            
    # Arquivos padrão se não existirem
    ws_path = os.path.join(agents_dir, "workspace")
    os.makedirs(ws_path, exist_ok=True)
    for fn, content in [("SOUL.md", f"Você é {config['name']}."), ("MEMORY.md", "# MEMória")]:
        p = os.path.join(ws_path, fn)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f: f.write(content)

    return {"success": True, "agent": config}

@app.delete("/api/agents/{agent_id}")
async def delete_agent_api(agent_id: str):
    if agent_id.lower() == "moltyclaw": raise HTTPException(403, "Não pode deletar master")
    import shutil
    p = os.path.join(MOLTY_DIR, "agents", agent_id)
    if os.path.exists(p):
        shutil.rmtree(p)
        return {"success": True}
    return {"error": "Não encontrado"}

@app.get("/api/agent/{file_type}")
async def get_agent_file(file_type: str, agent: str = "MoltyClaw"):
    allowed = {"memory": "MEMORY.md", "soul": "SOUL.md", "identity": "IDENTITY.md", "user": "USER.md", "bootstrap": "BOOTSTRAP.md"}
    if file_type not in allowed: raise HTTPException(400, "Arquivo inválido")
    
    base = MOLTY_DIR if agent == "MoltyClaw" else os.path.join(MOLTY_DIR, "agents", agent)
    path = os.path.join(base, "workspace", allowed[file_type])
    
    # Migração fallback
    if not os.path.exists(path):
        old_path = os.path.join(base, allowed[file_type])
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            import shutil
            shutil.move(old_path, path)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": f"# {file_type.upper()}\n\nConteúdo não inicializado."}

@app.post("/api/agent/{file_type}")
async def save_agent_file(file_type: str, data: Dict[str, str], agent: str = Query("MoltyClaw")):
    allowed = {"memory": "MEMORY.md", "soul": "SOUL.md", "identity": "IDENTITY.md", "user": "USER.md", "bootstrap": "BOOTSTRAP.md"}
    if file_type not in allowed: raise HTTPException(400, "Arquivo inválido")
    
    base = MOLTY_DIR if agent == "MoltyClaw" else os.path.join(MOLTY_DIR, "agents", agent)
    ws_path = os.path.join(base, "workspace")
    os.makedirs(ws_path, exist_ok=True)
    
    with open(os.path.join(ws_path, allowed[file_type]), "w", encoding="utf-8") as f:
        f.write(data.get("content", ""))
    return {"success": True}

@app.post("/api/agent/import_context")
async def import_context_api(data: Dict[str, str]):
    if not ready: raise HTTPException(503, "O agente não está pronto.")
    imported_data = data.get("context", "")
    if not imported_data: raise HTTPException(400, "Nenhum dado fornecido.")
    
    memory_path = os.path.join(MOLTY_DIR, 'workspace', 'MEMORY.md')
    if not os.path.exists(memory_path):
         memory_path = os.path.join(MOLTY_DIR, 'MEMORY.md')
         
    current_memory = ""
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f: current_memory = f.read()
    
    prompt = f"REGRAS DE ASSIMILAÇÃO:\n1. Preserve fatos.\n2. Não duplique.\nRetorne apenas o novo MARKDOWN revisado para o MEMORY.md.\n\nATUAL:\n{current_memory}\n\nIMPORTADO:\n{imported_data}"
    
    try:
        new_content = await master_agent.ask(prompt=prompt, silent=True)
        new_content = new_content.replace("```markdown", "").replace("```", "").strip()
        with open(memory_path, "w", encoding="utf-8") as f: f.write(new_content)
        return {"success": True, "new_content": new_content}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

# --- Routing / Bindings ---

@app.get("/api/bindings")
async def get_bindings():
    from routing import load_bindings
    return load_bindings()

@app.post("/api/bindings")
async def save_bindings_api(data: Dict[str, Any]):
    from routing import save_bindings
    save_bindings(data)
    return {"success": True}

# --- Skills & MCP (Ported) ---

@app.get("/api/skills")
async def get_skills_api(workspace: str = ""):
    all_skills = skills.load_skill_entries(workspace)
    return {"skills": [{
        "name": s.name, "description": s.description, "emoji": s.emoji, "source": s.source,
        "eligible": s.eligible, "reason": s.eligibility_reason, "requires": s.requires
    } for s in all_skills]}

@app.post("/api/skills/install")
async def install_skill_api(data: Dict[str, str]):
    source = data.get("source")
    if not source: raise HTTPException(400, "Source required")
    success, msg = skills.install_skill(source)
    if success: return {"success": True, "message": msg}
    raise HTTPException(500, detail=msg)

@app.get("/api/mcp/list")
async def list_mcps():
    catalog = [
        {"id": "magic-mcp", "name": "Magic MCP", "description": "Ferramentas 21st-dev.", "command": "moltyclaw mcp install", "args": ["https://github.com/21st-dev/magic-mcp"]},
        {"id": "boost-mcp", "name": "Boost MCP", "description": "Servidor Community.", "command": "moltyclaw mcp install", "args": ["https://github.com/boost-community/boost-mcp"]},
        # ... podem ser adicionados mais aqui
    ]
    installed_ids = []
    p = os.path.join(MOLTY_DIR, "mcp_servers.json")
    if os.path.exists(p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
                installed_ids = list(d.get("mcpServers", {}).keys())
        except: pass
    return {"mcps": catalog, "installed": installed_ids}

@app.post("/api/mcp/install")
async def install_mcp_api(data: Dict[str, Any]):
    mcp_args = data.get("args", [])
    if not mcp_args: raise HTTPException(400, "Repo URL required")
    repo_url = mcp_args[0]
    import subprocess
    try:
        subprocess.run(f'"{sys.executable}" "{os.path.join(BASE_DIR, "..", "start_moltyclaw.py")}" mcp install {repo_url}', shell=True, check=True)
        return {"success": True}
    except:
        raise HTTPException(500, detail="Falha na instalação via CLI")

@app.get("/api/scheduler/jobs")
async def get_scheduler_jobs():
    return {"jobs": scheduler.jobs if scheduler else []}

@app.post("/api/scheduler/add")
async def add_scheduler_job(data: Dict[str, Any]):
    if not scheduler: raise HTTPException(503, "Scheduler offline")
    job = scheduler.add_job(
        name=data.get("name"), description=data.get("description"),
        interval_min=data.get("interval_min", 15), payload=data.get("payload", "")
    )
    return {"success": True, "job": job}

# --- Main ---

if __name__ == "__main__":
    host = "0.0.0.0" if os.environ.get("MOLTY_WEBUI_SHARE") == "1" else "127.0.0.1"
    port = 5000
    console.print(f"[bold magenta]🚀 MoltyClaw Gateway subindo em http://{host}:{port}[/bold magenta]")
    uvicorn.run(app, host=host, port=port)
