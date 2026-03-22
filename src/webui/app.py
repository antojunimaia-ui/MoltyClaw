import os
import sys
import asyncio
import threading
import json
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Silenciar spams do flask no console

# Adiciona o diretório base para ler os imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.moltyclaw import MoltyClaw
from rich.console import Console

console = Console()
MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")
app = Flask(__name__, template_folder="templates", static_folder="static")
load_dotenv()

agent = None
loop = None
ready = False

def run_agent_loop():
    global agent, loop, ready
    
    # Prepara o Event Loop do Asyncio para a Thread 
    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    agent = MoltyClaw(name="MoltyClaw (WebUI Gateway)")
    
    # Inicia o Browser do Playwright escondido
    loop.run_until_complete(agent.init_browser())
    
    # Se existirem servidores MCP, inicia e conecta via IO Pipe
    if agent.mcp_hub:
        loop.run_until_complete(agent.mcp_hub.connect_servers())
    
    ready = True
    console.print("\n[bold green]✅ WebUI Health OK -> Porta 5000 Aberta![/bold green]")
    loop.run_forever()

# Inicia o Loop do MoltyClaw silenciosamente debaixo dos panos numa thread dedicada
threading.Thread(target=run_agent_loop, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"ready": ready})

from werkzeug.utils import secure_filename
from flask import send_from_directory
import queue
import json
import re

@app.route("/temp/<path:filename>")
def serve_temp(filename):
    return send_from_directory(os.path.abspath(os.path.join(MOLTY_DIR, "temp")), filename)

agent_instances = {}

def get_or_create_agent(agent_id="MoltyClaw"):
    global agent, ready
    if agent_id == "MoltyClaw":
        return agent
    
    if agent_id not in agent_instances:
        console.print(f"[info]🆕 Criando instância para sub-agente: {agent_id}[/info]")
        # Busca config para pegar o nome real se existir
        agents_dir = os.path.join(MOLTY_DIR, "agents", agent_id)
        name = agent_id
        if os.path.exists(os.path.join(agents_dir, "config.json")):
            try:
                with open(os.path.join(agents_dir, "config.json"), "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    name = cfg.get("name", agent_id)
            except: pass
        
        # Carrega o .env do agente para o ambiente temporariamente se existir
        env_path = os.path.join(agents_dir, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)

        new_agent = MoltyClaw(name=name, agent_id=agent_id)
        # O sub-agente no WebUI compartilha o browser do gateway (via CDP)
        fut = asyncio.run_coroutine_threadsafe(new_agent.init_browser(), loop)
        fut.result(timeout=30)
        
        agent_instances[agent_id] = new_agent
        
    return agent_instances[agent_id]

@app.route("/api/chat", methods=["POST"])
def chat():
    if not ready:
         return jsonify({"error": "Gateway MoltyClaw está ligando o Browser... Aguarde 5 segundos."}), 503
         
    if request.is_json:
        user_msg = request.json.get("message", "")
        req_agent_id = request.json.get("agent_id", "MoltyClaw")
    else:
        user_msg = request.form.get("message", "")
        req_agent_id = request.form.get("agent_id", "MoltyClaw")
        
    target_agent = get_or_create_agent(req_agent_id)
    
    uploaded_file = request.files.get("file")
    if uploaded_file and uploaded_file.filename:
        os.makedirs(os.path.join(MOLTY_DIR, "temp"), exist_ok=True)
        filename = secure_filename(uploaded_file.filename)
        filepath = os.path.join(MOLTY_DIR, "temp", f"webui_{filename}")
        uploaded_file.save(filepath)
        user_msg += f"\n\n[SISTEMA: O usuário acabou de te enviar via WebUI o seguinte arquivo. Caminho salvo com sucesso: {os.path.abspath(filepath)}]"
        
        ext = filename.split(".")[-1].lower()
        if ext in ['mp3', 'ogg', 'wav', 'm4a']:
            try:
                # Roda a transcrição na thread do asyncio usando o agente alvo
                fut = asyncio.run_coroutine_threadsafe(target_agent.transcribe_audio(filepath), loop)
                text = fut.result(timeout=60)
                if text:
                    user_msg += f"\n(Áudio Anexado Transcrito usando Voxtral Mini): '{text}'"
            except Exception as e:
                console.print(f"[warning]Erro na transcrição de áudio: {e}[/warning]")

    if not user_msg:
        return jsonify({"error": "Mensagem vazia."}), 400

    q = queue.Queue()

    async def stream_cb(token: str):
        q.put(("token", token))

    async def tool_cb(msg: str):
        q.put(("tool", msg))

    async def run_ask():
        try:
            res = await target_agent.ask(prompt=user_msg, silent=False, stream_callback=stream_cb, tool_callback=tool_cb)
            if res and isinstance(res, str) and "[AUDIO_REPLY:" in res:
                match = re.search(r'\[AUDIO_REPLY:\s*([^\]]+)\]', res)
                if match:
                    filename = os.path.basename(match.group(1).strip())
                    q.put(("token", f"\n\n[AUDIO_REPLY: {filename}]\n\n"))
                    
            q.put(("done", None))
        except Exception as e:
            q.put(("error", str(e)))

    asyncio.run_coroutine_threadsafe(run_ask(), loop)

    def generate():
        while True:
            evt_type, data = q.get()
            if evt_type == "done":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break
            elif evt_type == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': data})}\n\n"
                break
            else:
                yield f"data: {json.dumps({'type': evt_type, 'content': data})}\n\n"

    from flask import Response, stream_with_context
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

import subprocess
active_processes = {}

def start_integration(name, agent_id="MoltyClaw"):
    cmd_map = {
        "whatsapp": ["python src/integrations/whatsapp_server.py", "node src/integrations/whatsapp_bridge.js"],
        "discord": ["python src/integrations/discord_bot.py"],
        "telegram": ["python src/integrations/telegram_bot.py"],
        "twitter": ["python src/integrations/twitter_bot.py"],
        "bluesky": ["python src/integrations/bluesky_bot.py"]
    }
    
    if name not in cmd_map: return False
    
    # Busca o nome real do agente
    agent_name = agent_id
    if agent_id != "MoltyClaw":
        config_path = os.path.join(MOLTY_DIR, "agents", agent_id, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    agent_name = cfg.get("name", agent_id)
            except: pass

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # Carrega .env do agente se for um sub-agente
    if agent_id != "MoltyClaw":
        agent_env = os.path.join(MOLTY_DIR, "agents", agent_id, ".env")
        if os.path.exists(agent_env):
            load_dotenv(agent_env, override=True)
            # Como a Popen herda o env atual de quem chama se não passarmos, 
            # e load_dotenv mexe no os.environ do processo ATUAL (app.py),
            # precisamos garantir que o env do Popen reflita isso.
            env = os.environ.copy()

    if name == "whatsapp": env["MOLTY_WHATSAPP_ACTIVE"] = "1"
    if name == "discord": env["MOLTY_DISCORD_ACTIVE"] = "1"
    if name == "telegram": env["MOLTY_TELEGRAM_ACTIVE"] = "1"
    if name == "twitter": env["MOLTY_TWITTER_ACTIVE"] = "1"
    if name == "bluesky": env["MOLTY_BLUESKY_ACTIVE"] = "1"
    
    procs = []
    for base_cmd in cmd_map[name]:
        # Adiciona argumentos de agente se for script python
        cmd = base_cmd
        if cmd.startswith("python"):
            cmd += f' --agent "{agent_id}" --name "{agent_name}"'
            
        p = subprocess.Popen(cmd, shell=True, env=env)
        procs.append(p)
    
    # Chave única por integração e agente para permitir múltiplos agentes simultâneos
    key = f"{name}_{agent_id}"
    active_processes[key] = procs
    return True

def stop_integration(name, agent_id="MoltyClaw"):
    key = f"{name}_{agent_id}"
    if key in active_processes:
        for p in active_processes[key]:
            p.terminate()
        active_processes.pop(key, None)
        return True
    return False

@app.route("/api/integrations", methods=["GET"])
def get_integrations():
    # Retorna o status de quais integrações estão ativas e para qual agente
    status = {}
    for key, procs in active_processes.items():
        if any(p.poll() is None for p in procs):
            # Decompõe a chave ex: discord_MoltyClaw
            parts = key.split("_")
            int_name = parts[0]
            agent_id = "_".join(parts[1:])
            if int_name not in status: status[int_name] = []
            status[int_name].append(agent_id)
            
    return jsonify(status)

@app.route("/api/integrations/<action>", methods=["POST"])
def toggle_integration(action):
    data = request.json
    name = data.get("name")
    agent_id = data.get("agent_id", "MoltyClaw")
    
    if action == "start":
        succ = start_integration(name, agent_id)
    elif action == "stop":
        succ = stop_integration(name, agent_id)
    else:
        return jsonify({"error": "Ação inválida"}), 400
        
    if succ:
        return jsonify({"success": True})
    return jsonify({"error": "Falha na operação"}), 500

@app.route("/api/agent/<file>", methods=["GET", "POST"])
def manage_agent_file(file):
    if file not in ["memory", "soul"]:
        return jsonify({"error": "Arquivo inválido"}), 400
        
    agent_id = request.args.get("agent", "MoltyClaw")
    
    if agent_id == "MoltyClaw":
        folder_path = MOLTY_DIR
    else:
        folder_path = os.path.join(MOLTY_DIR, "agents", agent_id)
        os.makedirs(folder_path, exist_ok=True)
        
    filename = "MEMORY.md" if file == "memory" else "SOUL.md"
    filepath = os.path.join(folder_path, filename)
    
    if request.method == "GET":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return jsonify({"content": content})
        except FileNotFoundError:
            # For new agents, provide a default template
            if file == "soul":
                default_content = f"Você é {agent_id}, um agente especializado.\n\nSiga sempre as diretrizes de autonomia."
                return jsonify({"content": default_content})
            return jsonify({"content": "# MEMÓRIA\n\nNenhuma memória armazenada ainda."})
            
    if request.method == "POST":
        data = request.json
        content = data.get("content", "")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return jsonify({"success": True})

@app.route("/api/bindings", methods=["GET", "POST"])
def manage_bindings():
    from routing import load_bindings, save_bindings
    if request.method == "GET":
        return jsonify(load_bindings())
    if request.method == "POST":
        bindings = request.json
        save_bindings(bindings)
        return jsonify({"success": True})

@app.route("/api/agents", methods=["GET"])
def get_agents():
    agents_dir = os.path.join(MOLTY_DIR, "agents")
    os.makedirs(agents_dir, exist_ok=True)
    
    agent_list = [
        {
            "id": "MoltyClaw",
            "name": "MoltyClaw",
            "description": "Agente Mestre Orquestrador.",
            "provider": "Padrao do Kernel",
            "tools_mcp": ["Todos"],
            "tools_local": ["Todas"],
            "is_master": True
        }
    ]
    
    for agent_id in os.listdir(agents_dir):
        agent_path = os.path.join(agents_dir, agent_id)
        if os.path.isdir(agent_path):
            config_path = os.path.join(agent_path, "config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    cfg["id"] = agent_id
                    cfg["is_master"] = False
                    agent_list.append(cfg)
                except: pass
    
    return jsonify({"agents": agent_list})

@app.route("/api/agents", methods=["POST"])
def save_agent():
    data = request.json
    agent_id = data.get("id") or data.get("name", "").replace(" ", "_").lower()
    
    if not agent_id or agent_id.lower() == "moltyclaw":
        return jsonify({"error": "Nome inválido ou reservado."}), 400
        
    agents_dir = os.path.join(MOLTY_DIR, "agents", agent_id)
    os.makedirs(agents_dir, exist_ok=True)
    
    config = {
        "name": data.get("name", agent_id),
        "description": data.get("description", "Agente Especializado do MoltyClaw."),
        "provider": data.get("provider", "mistral"),
        "tools_mcp": data.get("tools_mcp", []),
        "tools_local": data.get("tools_local", ["DDG_SEARCH", "READ_PAGE"])
    }
    
    with open(os.path.join(agents_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
        
    # Salvar a Env do agente
    env_vars = data.get("env_vars", {})
    with open(os.path.join(agents_dir, ".env"), "w", encoding="utf-8") as f:
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")
            
    # Criar SOUL padrao se não houver
    soul_path = os.path.join(agents_dir, "SOUL.md")
    if not os.path.exists(soul_path):
        with open(soul_path, "w", encoding="utf-8") as f:
            f.write(f"Você é {config['name']}, um agente especializado.\n\n"
                    f"Descrição: {config['description']}\n\n"
                    f"Seja preciso nas suas atividades.")
                    
    memory_path = os.path.join(agents_dir, "MEMORY.md")
    if not os.path.exists(memory_path):
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write("# MEMORY\n\nA memória deste agente está limpa.")
            
    return jsonify({"success": True, "agent": config})

@app.route("/api/agents/<agent_id>", methods=["DELETE"])
def delete_agent(agent_id):
    if agent_id.lower() == "moltyclaw":
        return jsonify({"error": "Não é permitido excluir o MoltyClaw Master."}), 403
        
    import shutil
    agent_dir = os.path.join(MOLTY_DIR, "agents", agent_id)
    if os.path.exists(agent_dir):
        shutil.rmtree(agent_dir)
        return jsonify({"success": True})
    return jsonify({"error": "Agente não encontrado."}), 404

@app.route("/api/agent/import_context", methods=["POST"])
def import_context():
    if not ready:
        return jsonify({"error": "Agente não está pronto."}), 503
        
    data = request.json
    imported_data = data.get("context", "")
    if not imported_data:
        return jsonify({"error": "Nenhum dado fornecido."}), 400
        
    # Caminho do MEMORY.md
    memory_path = os.path.join(MOLTY_DIR, 'MEMORY.md')
    current_memory = ""
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            current_memory = f.read()
            
    # Prompt de Assimilação
    assimilation_prompt = f"""
Você é o Agente de Assimilação de Contexto do MoltyClaw.
O usuário está importando dados de contexto de outro agente/IA.
Seu objetivo é fundir esse novo contexto com o MEMORY.md atual do MoltyClaw.

REGRAS:
1. Preserve fatos importantes (Identidade, Carreira, Projetos).
2. Não duplique informações que já existem.
3. Se houver informações conflitantes, prefira as mais detalhadas.
4. Mantenha o estilo e estrutura Markdown do MEMORY.md original.
5. Retorne APENAS o novo conteúdo completo para o arquivo MEMORY.md. Não adicione comentários externos.

MEMORY.md ATUAL:
---
{current_memory}
---

DADOS IMPORTADOS PARA ASSIMILAR:
---
{imported_data}
---

Retorne o conteúdo revisado do MEMORY.md:
"""

    try:
        # Chama o agente para processar a fusão
        assert agent is not None, "Agent is not initialized"
        assert loop is not None, "Loop is not initialized"
        fut = asyncio.run_coroutine_threadsafe(
            agent.ask(prompt=assimilation_prompt, silent=True), 
            loop
        )
        new_memory_content = fut.result(timeout=120)
        
        # Limpa blocos de código se o modelo teimar em colocar
        new_memory_content = new_memory_content.replace("```markdown", "").replace("```", "").strip()
        
        # Salva o novo MEMORY.md
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(new_memory_content)
            
        return jsonify({"success": True, "new_content": new_memory_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/mcp/list", methods=["GET"])
def list_mcps():
    mcps_from_api = [
        {
            "id": "magic-mcp",
            "name": "Magic MCP",
            "description": "Ferramentas incríveis da 21st-dev.",
            "command": "moltyclaw mcp install",
            "args": ["https://github.com/21st-dev/magic-mcp"]
        },
        {
            "id": "boost-mcp",
            "name": "Boost MCP",
            "description": "Servidor MCP pela Boost Community.",
            "command": "moltyclaw mcp install",
            "args": ["https://github.com/boost-community/boost-mcp"]
        },
        {
            "id": "mcp-server-canva",
            "name": "Canva MCP",
            "description": "Documentação Oficial de Server da Canva - Exemplo",
            "command": "moltyclaw mcp install",
            "args": ["https://www.canva.dev/docs/apps/mcp-server/"]
        },
        {
            "id": "mcp-server-cloudflare",
            "name": "Cloudflare MCP",
            "description": "Integração oficial de Server MCP da Cloudflare.",
            "command": "moltyclaw mcp install",
            "args": ["https://github.com/cloudflare/mcp-server-cloudflare"]
        }
    ]

    installed_ids = []
    mcp_path = os.path.join(MOLTY_DIR, "mcp_servers.json")
    if os.path.exists(mcp_path):
        try:
            with open(mcp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                installed_ids = list(data.get("mcpServers", {}).keys())
        except:
            pass
            
    return jsonify({"mcps": mcps_from_api, "installed": installed_ids})

@app.route("/api/mcp/install", methods=["POST"])
def install_mcp():
    data = request.json
    mcp_id = data.get("id")
    mcp_args = data.get("args", [])
    
    if not mcp_id or not mcp_args:
        return jsonify({"error": "Dados inválidos."}), 400
        
    repo_url = mcp_args[0]
    
    import subprocess
    try:
        # Chama a execução nativa do MoltyClaw para Clonar & Fazer Build do MCP!
        subprocess.run(
            f"python start_moltyclaw.py mcp install {repo_url}",
            shell=True,
            check=True
        )
        return jsonify({"success": True})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Falha na instalação via CLI."}), 500

if __name__ == "__main__":
    host = "0.0.0.0" if os.environ.get("MOLTY_WEBUI_SHARE") == "1" else "127.0.0.1"
    
    if host == "0.0.0.0":
        import socket
        local_ip = "SEU-IP-LOCAL"
        try:
            # Trick to get the actual local IP address routing to internet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            pass
            
        console.print("[intense_cyan]🚀 Acordando MoltyClaw WebUI Aberta para a Rede/Tailscale![/intense_cyan]")
        console.print(f"[intense_cyan]🌐 Acesse pelo celular usando: http://{local_ip}:5000[/intense_cyan]")
    else:
        console.print("[intense_cyan]🚀 Acordando MoltyClaw WebUI Privada... Acesse: http://127.0.0.1:5000[/intense_cyan]")
        console.print("[dim]Quer acessar do celular na rede? Use: moltyclaw web --share[/dim]")
        
    app.run(host=host, port=5000, debug=False, use_reloader=False)
