import os
import asyncio
import traceback
import re
import time
import shutil
import json
import websockets
import subprocess
import sys

# Adiciona o diretório src ao path para imports relativos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from initializer import initialize_moltyclaw, MOLTY_DIR
initialize_moltyclaw()

from playwright.async_api import async_playwright
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), "integrations"))
try:
    from integrations.mcp_hub import MCPHub
except ImportError:
    MCPHub = None

from system_prompt import build_system_prompt
from config_loader import get_config
from skills import (
    load_skill_entries,
    build_skills_metadata_prompt,
    find_skill_by_name,
    load_skill_body
)
from scheduler import SchedulerManager
from heartbeat import HeartbeatManager

try:
    from mistralai import Mistral
    # Na versão nova, usamos dicionários simples ou modelos específicos.
    ChatMessage = None 
except ImportError:
    try:
        from mistralai.async_client import MistralAsyncClient as Mistral  # type: ignore
        from mistralai.models.chat_completion import ChatMessage  # type: ignore
    except ImportError:
        Mistral = None
        ChatMessage = None

from openai import AsyncOpenAI
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import ollama
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:
    ollama = None
    OllamaAsyncClient = None

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.theme import Theme

load_dotenv(os.path.join(MOLTY_DIR, '.env'))

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "moltyclaw": "bold green",
    "user": "bold blue"
})
console = Console(theme=custom_theme)

class MoltyClaw:
    def __init__(self, name="MoltyClaw", agent_id=None, channel=None):
        self.name = name
        self.agent_id = agent_id if agent_id else (name.replace(" (WebUI Gateway)", "").replace(" (Discord)", "").replace(" (Telegram)", "").replace(" (WhatsApp)", "").replace(" (Twitter)", "").replace(" (Bluesky)", "").strip())
        if self.agent_id.startswith("MoltyClaw"): self.agent_id = "MoltyClaw"
        self.is_master = (self.agent_id == "MoltyClaw")

        # Detecta o canal pelo nome se não informado explicitamente
        # Ex: "MoltyClaw (Telegram)" → "telegram"
        if channel:
            self.channel = channel.lower()
        else:
            _name_lower = name.lower()
            if "telegram" in _name_lower:   self.channel = "telegram"
            elif "discord" in _name_lower:  self.channel = "discord"
            elif "whatsapp" in _name_lower: self.channel = "whatsapp"
            elif "twitter" in _name_lower:  self.channel = "twitter"
            elif "bluesky" in _name_lower:  self.channel = "bluesky"
            elif "webui" in _name_lower:    self.channel = "webui"
            elif "cmd" in _name_lower:      self.channel = "cli"
            else:                           self.channel = None
        
        self.base_dir = MOLTY_DIR if self.is_master else os.path.join(MOLTY_DIR, "agents", self.agent_id)
        self.workspace_dir = os.path.join(self.base_dir, "workspace")
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Carrega configuração do agente (tools permitidas, provider, etc)
        self.config = self._load_agent_config()
        self.allowed_tools_local = set(self.config.get("tools_local", [])) if not self.is_master else None
        self.allowed_tools_mcp = set(self.config.get("tools_mcp", [])) if not self.is_master else None
        
        # Carrega o .env específico do agente se existir
        if not self.is_master:
            agent_env = os.path.join(self.base_dir, ".env") # .env continua na raiz do agente
            if os.path.exists(agent_env):
                console.print(f"[dim]>> Carregando configurações específicas do agente em {agent_env}[/dim]")
                load_dotenv(agent_env, override=True)
        
        # Le a variavel de ambiente passada (ou do config do agente)
        self.provider = self.config.get("provider", os.getenv("MOLTY_PROVIDER", "mistral"))
        
        # Debug: mostra qual provider foi carregado
        if self.is_master:
            console.print(f"[dim]>> [{self.name}] Provider inicializado: {self.provider}[/dim]")
        
        # Carrega Configuração Global do moltyclaw.json
        molty_config = get_config()
        
        def get_key_for(prov):
            p_cfg = molty_config.get("providers", {}).get(prov, {})
            if prov == "mistral": return p_cfg.get("api_key") or os.getenv("MISTRAL_API_KEY")
            if prov == "gemini":  return p_cfg.get("api_key") or os.getenv("GEMINI_API_KEY")
            if prov == "ollama":  return "ollama" # Ollama não exige chave, mas usamos placeholder
            if prov == "kodacloud": return "kodacloud" # Koda Cloud não exige chave
            return p_cfg.get("api_key") or os.getenv("OPENROUTER_API_KEY")

        # --- Lógica de Smart Provider (Auto-Discovery) ---
        self.api_key = get_key_for(self.provider)
        
        # Se não tem a chave do provedor escolhido, tenta achar qualquer outra disponível
        if not self.api_key:
            for fallback in ["kodacloud", "gemini", "mistral", "openrouter", "ollama"]:
                if fallback == self.provider: continue
                fallback_key = get_key_for(fallback)
                if fallback_key:
                    console.print(f"[dim]>> [{self.name}] Provedor '{self.provider}' sem chave. Chave de '{fallback}' detectada. Alternando automaticamente...[/dim]")
                    self.provider = fallback
                    self.api_key = fallback_key
                    break

        p_cfg = molty_config.get("providers", {}).get(self.provider, {})
        if self.provider == "mistral":
            self.model = p_cfg.get("model") or os.getenv("MISTRAL_MODEL", "mistral-medium")
        elif self.provider == "gemini":
            self.model = p_cfg.get("model") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        elif self.provider == "ollama":
            self.model = p_cfg.get("model") or os.getenv("OLLAMA_MODEL", "llama3")
        elif self.provider == "kodacloud":
            self.model = p_cfg.get("model") or os.getenv("KODACLOUD_MODEL", "gemini-2.5-flash")
        else:
            self.model = p_cfg.get("model") or os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash")
        
        # Debug: mostra qual modelo foi carregado
        if self.is_master:
            console.print(f"[dim]>> [{self.name}] Modelo carregado: {self.model}[/dim]")
        
        # Preferência do Navegador (Ativado/Desativado por comando CLI)
        self.browser_enabled = molty_config.get("browser", {}).get("enabled", True)
        self.browser_headless = molty_config.get("browser", {}).get("headless", True)
        
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        # Callback para anunciar resultado de sub-agentes de volta ao canal (Telegram, Discord...)
        # É preenchido pelo ask() quando vem do gateway (telegram_bot, discord_bot, etc.)
        self._current_reply_callback = None
        # Inicializa MCPHub com lista de servidores permitidos (se for sub-agente)
        if MCPHub:
            if self.is_master:
                self.mcp_hub = MCPHub()  # Master tem acesso a todos
            else:
                self.mcp_hub = MCPHub(allowed_servers=self.allowed_tools_mcp)  # Sub-agente tem lista restrita
        else:
            self.mcp_hub = None
        
        # Constrói a lista de ferramentas disponíveis baseado nas permissões do agente
        active_features = self._build_tools_list()
        
        # Carrega SOUL.md, IDENTITY.md, USER.md, BOOTSTRAP.md e MEMORY.md específicos do agente
        soul_content = self._load_soul()
        identity_content = self._load_identity()
        user_content = self._load_user()
        bootstrap_content = self._load_bootstrap()
        memory_content = self._load_memory()

        # Carregamento do Sistema de Skills
        self.skills = load_skill_entries(self.workspace_dir)
        skills_prompt = build_skills_metadata_prompt(self.skills)

        self.history = [
            {"role": "system", "content": build_system_prompt(
                name=self.name,
                agent_id=self.agent_id,
                model=self.model,
                provider=self.provider,
                workspace_dir=self.workspace_dir,
                soul_content=soul_content,
                identity_content=identity_content,
                user_content=user_content,
                bootstrap_content=bootstrap_content,
                memory_content=memory_content,
                active_features=active_features,
                skills_prompt=skills_prompt,
                mcp_placeholder=self._get_mcp_prompt_placeholder(),
                channel=self.channel,
                is_subagent=not self.is_master,
            )}
        ]
        
        if not self.api_key:
            console.print(f"[{self.name}] [warning]Aviso: Chave de API para provedor {self.provider} não encontrada ({'MISTRAL_API_KEY' if self.provider == 'mistral' else 'OPENROUTER_API_KEY'}).[/warning]")
            self.mistral_client = None
            self.openai_client = None
            self.gemini_client = None
        else:
            if self.provider == "mistral":
                # Detecta se é a versão nova (Mistral) ou antiga (MistralAsyncClient)
                try:
                    from mistralai import Mistral
                    self.mistral_client = Mistral(api_key=self.api_key)
                except (ImportError, TypeError):
                    from mistralai.async_client import MistralAsyncClient  # type: ignore
                    self.mistral_client = MistralAsyncClient(api_key=self.api_key)
                self.openai_client = None
                self.gemini_client = None
            elif self.provider == "gemini":
                if genai:
                    genai.configure(api_key=self.api_key)
                    self.gemini_client = genai.GenerativeModel(
                        model_name=self.model,
                        system_instruction=self.history[0]["content"] if len(self.history) > 0 else None
                    )
                else:
                    self.gemini_client = None
                self.mistral_client = None
                self.openai_client = None
            elif self.provider == "ollama":
                if OllamaAsyncClient:
                    self.ollama_client = OllamaAsyncClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))
                else:
                    self.ollama_client = None
                self.mistral_client = None
                self.gemini_client = None
                self.openai_client = None
            elif self.provider == "kodacloud":
                # Koda Cloud usa API compatível com OpenAI mas com endpoint /v1/chat
                self.ollama_client = None
                self.mistral_client = None
                self.gemini_client = None
                self.openai_client = AsyncOpenAI(
                    base_url="http://cn-01.hostzera.com.br:2137/v1",
                    api_key="not-needed",  # Koda Cloud não requer API key
                )
                # Sobrescreve o endpoint para usar /chat em vez de /chat/completions
                self.kodacloud_endpoint = "http://cn-01.hostzera.com.br:2137/v1/chat"
            else:
                self.ollama_client = None
                self.mistral_client = None
                self.gemini_client = None
                self.openai_client = AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.api_key,
                )
        self.is_busy = False # Flag para o Heartbeat/Background tasks
        self.pty_bridge_process = None
        self.pty_output = ""
        
        # Inicializa o Motor de Agendamento Proativo
        self.scheduler = SchedulerManager(self, base_dir=self.base_dir)
        self.heartbeat = HeartbeatManager(self)

    def _get_mcp_prompt_placeholder(self) -> str:
        return "[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]"

    async def update_mcp_tools_in_prompt(self):
        if not self.mcp_hub:
            return
            
        tools_str = await self.mcp_hub.get_all_tools_formatted()
        if not tools_str:
            return
            
        mcp_section = f"\nFERRAMENTAS MCP EXTRAS DETECTADAS VIA SERVIDOR EXTERNO (Protocolo MCP):\n{tools_str}\n"
        
        # Encontra a posição do base_prompt e substitui a TAG
        prompt_content = self.history[0]["content"]
        if "[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]" in prompt_content:
            self.history[0]["content"] = prompt_content.replace("[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]", mcp_section)
        else:
            # Caso ja tenha injetado, tira a velha e bota a nova limpando a string
            import re
            new_content = re.sub(r'\nFERRAMENTAS MCP EXTRAS DETECTADAS.*?(\n\n|$)', lambda m: '\n' + mcp_section + '\n\n', prompt_content, flags=re.DOTALL)
            self.history[0]["content"] = new_content

    async def start_background_services(self):
        """Inicia Heartbeat e Scheduler em tarefas paralelas de background."""
        if self.is_master:
            # Apenas o Master (ou agente principal logado) roda esses motores globalmente
            # Mas podemos permitir por agente se quiser proatividade individual.
            asyncio.create_task(self.scheduler.run())
            asyncio.create_task(self.heartbeat.run())
            # Inicia o PTY Bridge (Node.js) se estiver na pasta correta
            await self.start_pty_bridge()
            console.print(f"[bold green]🚀 [{self.name}] Motores Proativos (Scheduler, Heartbeat & PTY Bridge) iniciados![/bold green]")

    async def start_pty_bridge(self):
        """Inicia a ponte persistente do terminal (node-pty)."""
        bridge_path = os.path.join(os.path.dirname(__file__), "terminal", "pty_bridge.js")
        if not os.path.exists(bridge_path):
            return
            
        try:
            # Tenta ver se já tem algo na porta 9001 (evitar conflito)
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', 9001)) == 0:
                    console.print("[dim]>> [PTY Master] Ponte PTY já detectada na porta 9001. Reusando...[/dim]")
                    return
            
            console.print(f"[dim]>> [PTY Master] Inicializando Ponte PTY persistente (node-pty)...[/dim]")
            self.pty_bridge_process = await asyncio.create_subprocess_shell(
                f"node {bridge_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.sleep(2.0) # Tempo pro Node subir
        except Exception as e:
            console.print(f"[warning]Falha ao iniciar PTY Bridge: {e}[/warning]")

    async def close_browser(self):
        try:
            if self.page: await self.page.close()
            if self.context: await self.context.close()
            if self.browser: await self.browser.close()
            if self.playwright: await self.playwright.stop()
            if self.mcp_hub: await self.mcp_hub.cleanup()
        except: pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    async def init_browser(self):
        """Inicializa ou Conecta ao navegador compartilhado via CDP (Porta 9222)."""
        if not self.browser_enabled:
            return
            
        await self.close_browser() 
        import aiohttp
        import random
        import socket
        
        cdp_url = "http://localhost:9222"

        # ── Passo 1: Verifica se o browser já está rodando ANTES de tentar o lock ──
        # Se já estiver, conecta direto via CDP sem precisar do lock.
        async def _try_cdp_connect() -> bool:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{cdp_url}/json/version", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        if resp.status != 200:
                            return False
                if self.playwright is None:
                    self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                else:
                    self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                console.print(f"[info][{self.name}] 🔗 Conectado ao Navegador Compartilhado (Master já estava ativo)![/info]")
                return True
            except Exception:
                return False

        # Tenta conectar via CDP imediatamente
        if await _try_cdp_connect():
            return

        # ── Passo 2: Browser não está rodando — tenta ser o Master ──
        # Desincronização suave para evitar que múltiplos processos tentem ao mesmo tempo
        await asyncio.sleep(random.uniform(0.1, 1.5))

        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        has_lock = False

        for attempt in range(30):
            try:
                lock_socket.bind(('127.0.0.1', 9223))
                has_lock = True
                break
            except OSError:
                # Enquanto espera o lock, verifica se o master já subiu o browser
                if attempt > 0 and attempt % 3 == 0:
                    if await _try_cdp_connect():
                        try:
                            lock_socket.close()
                        except Exception:
                            pass
                        return
                await asyncio.sleep(1.0)

        # Se não conseguiu o lock mas o browser subiu enquanto esperava, conecta via CDP
        if not has_lock:
            if await _try_cdp_connect():
                return
            console.print(f"[warning][{self.name}] Não foi possível obter o lock do browser. Abortando init_browser.[/warning]")
            return

        try:
            if self.playwright is None:
                self.playwright = await async_playwright().start()

            # Verifica uma última vez antes de lançar (outro processo pode ter subido no intervalo)
            if await _try_cdp_connect():
                return

            # Lê a configuração de headless
            molty_cfg = get_config()
            is_headless = molty_cfg.get("browser", {}).get("headless", True)
            
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=os.path.join(MOLTY_DIR, 'browser_profile'),
                headless=is_headless,
                ignore_default_args=["--enable-automation"],
                args=[
                    '--remote-debugging-port=9222',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--window-position=0,0'
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
                viewport={"width": 1366, "height": 768},
                locale='pt-BR',
                timezone_id='America/Sao_Paulo',
                color_scheme='dark'
            )
            
            self.browser = self.context.browser
            
            await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            
            try:
                from playwright_stealth import Stealth
                await Stealth().apply_stealth_async(self.context)
                console.print(f"[info][{self.name}] 🥷 Stealth Anti-Bot Mode Ativado no Browser Principal (Master)![/info]")
            except ImportError:
                pass
                
            console.print(f"[info][{self.name}] Navegador Master Inicializado na Porta 9222![/info]")
            
            # Aguarda o Chromium estabilizar antes de soltar o lock
            await asyncio.sleep(2.0)
        except Exception as e:
            console.print(f"[error]Erro ao iniciar navegador: {e}[/error]")
        finally:
            if has_lock:
                try:
                    lock_socket.close()
                except: pass

    async def execute_terminal_command(self, command: str) -> str:
        if os.environ.get("MOLTY_MODE", "private") == "public":
            console.print(f"[warning][{self.name}] Tentativa de uso de CMD intercedida pelo Modo Publico.[/warning]")
            return "Erro: O comando CMD está DESABILITADO no modo PUBLIC (ações de terminal bloqueadas por segurança)."
            
        console.print(f"[info][{self.name}] Terminal (PTY Session):[/info] {command}")
        
        # Tentativa de conexão via PTY Bridge (WebSocket) na porta 9001
        try:
            uri = "ws://localhost:9001"
            async with websockets.connect(uri) as websocket:
                # Envia o comando com Enter no final
                full_cmd = command + "\n"
                await websocket.send(json.dumps({"type": "input", "data": full_cmd}))
                
                # Aguarda o output por um tempo fixo (3s p/ comandos rápidos, ou até 10s para processos maiores)
                # Na verdade, como é persistente, coletamos os logs iniciais + o que vir depois do comando.
                output_acc = ""
                try:
                    # Lê o buffer inicial (limpa o que tinha antes?)
                    # Na verdade, a ponte envia o buffer completo no 'init'
                    while True:
                        msg = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        data = json.loads(msg)
                        if data['type'] == 'output' or data['type'] == 'init':
                            output_acc += data['data']
                            if len(output_acc) > 8000: # Limite de leitura por turno
                                break
                except asyncio.TimeoutError:
                    pass # Fine, output ended or paused
                
                # Limpeza simples de caracteres ANSI para o modelo não se confundir
                import re
                clean_output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output_acc)
                
                # Tenta isolar o output do SEU comando (heuristicamente pegando o final)
                return f"[Sessão Persistente Ativa]\n{clean_output[-4000:]}"
                
        except Exception as e:
            # Fallback para Subset-Processo se o PTY falhar
            console.print(f"[warning][{self.name}] PTY Bridge offline ({e}), usando fallback de subset-processo...[/warning]")
            try:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.workspace_dir
                )
                stdout, stderr = await process.communicate()
                output = stdout.decode("utf-8", errors="replace").strip()
                error = stderr.decode("utf-8", errors="replace").strip()
                if process.returncode != 0:
                    return f"Erro (código {process.returncode}):\n{error}"
                return output if output else "Comando executado com sucesso."
            except Exception as inner_e:
                return f"Exceção: {inner_e}"

    async def run_browser_action(self, action: str, param: str) -> str:
        if action == "OPEN_BROWSER":
            await self.init_browser()
            return "Navegador (re)inicializado com sucesso! Agora você pode usar GOTO, CLICK, etc."

        if not self.page or self.page.is_closed():
            return "Erro: O navegador está fechado ou não foi iniciado. Use a ferramenta OPEN_BROWSER primeiro!"
            
        try:
            # Limpa marcadores antes de qualquer nova ação (exceto INSPECT que cria novos)
            if action != "INSPECT_PAGE":
                try: await self.page.evaluate("document.querySelectorAll('.molty-visual-marker').forEach(el => el.remove())")
                except: pass

            if action == "GOTO":
                await self.page.goto(param, timeout=30000)
                await self.page.wait_for_load_state('domcontentloaded')
                title = await self.page.title()
                return f"Página carregada com sucesso. Título da Guia: {title}"
                
            elif action == "CLICK":
                await self.page.click(param, timeout=10000)
                await self.page.wait_for_timeout(2000)  # Aguarda animações ou reações do clique
                return f"Clique efetuado com sucesso no elemento: {param}"
                
            elif action == "TYPE":
                parts = param.split("|", 1)
                if len(parts) != 2:
                    return "Erro: Formato inválido para TYPE. Use [TYPE: seletor | texto]"
                selector = parts[0].strip()
                text = parts[1].strip()
                await self.page.fill(selector, text, timeout=10000)
                return f"Texto '{text}' digitado com sucesso no alvo '{selector}'"
                
            elif action == "PRESS_ENTER":
                await self.page.keyboard.press("Enter")
                await self.page.wait_for_timeout(2000)  # Aguarda animações ou submits após a tecla enter
                return "Tecla 'Enter' pressionada com sucesso!"

            elif action == "PRESS_KEY":
                await self.page.keyboard.press(param)
                await self.page.wait_for_timeout(1000)
                return f"Tecla '{param}' pressionada!"
                
            elif action == "READ_PAGE":
                # Avalia o innerText do body inteiro e pega algo cru e facil da IA ler
                content = await self.page.evaluate("document.body.innerText")
                return f"CONTEÚDO TEXTUAL DA PÁGINA ATUAL (truncado): {content[:4000]}"
                
            elif action == "INSPECT_PAGE":
                js_code = """() => {
                    try {
                        // Reset existing IDs and markers
                        document.querySelectorAll('[data-operant-id]').forEach(el => el.removeAttribute('data-operant-id'));
                        document.querySelectorAll('.molty-visual-marker').forEach(el => el.remove());
                        
                        const isVisible = (el) => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0 && 
                                   rect.top >= 0 && rect.top <= window.innerHeight &&
                                   rect.left >= 0 && rect.left <= window.innerWidth &&
                                   window.getComputedStyle(el).visibility !== 'hidden' &&
                                   window.getComputedStyle(el).display !== 'none';
                        };

                        const interactiveSelectors = [
                            'a', 'button', 'input', 'select', 'textarea', 
                            '[role="button"]', '[role="link"]', '[role="checkbox"]', 
                            '[role="tab"]', '[role="textbox"]', '[onclick]', '[contenteditable="true"]'
                        ];

                        const elements = Array.from(document.querySelectorAll(interactiveSelectors.join(',')))
                            .filter(isVisible)
                            .slice(0, 80);

                        let result = [];
                        elements.forEach((el, index) => {
                            const id = index + 1;
                            el.setAttribute('data-operant-id', id);
                            const rect = el.getBoundingClientRect();

                            // Cria o marcador visual (estilo Navegador Inteligente)
                            const marker = document.createElement('div');
                            marker.className = 'molty-visual-marker';
                            Object.assign(marker.style, {
                                position: 'fixed',
                                left: rect.left + 'px',
                                top: rect.top + 'px',
                                width: rect.width + 'px',
                                height: rect.height + 'px',
                                border: '2px solid #38bdf8',
                                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                                pointerEvents: 'none',
                                zIndex: '2147483647',
                                borderRadius: '3px',
                                boxSizing: 'border-box',
                                transition: 'all 0.2s ease'
                            });

                            const label = document.createElement('div');
                            label.innerText = id;
                            Object.assign(label.style, {
                                position: 'absolute',
                                top: '-12px',
                                left: '-12px',
                                background: '#38bdf8',
                                color: '#000',
                                fontSize: '11px',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontWeight: 'bold',
                                boxShadow: '0 2px 5px rgba(0,0,0,0.4)',
                                border: '1px solid #fff'
                            });
                            marker.appendChild(label);
                            document.body.appendChild(marker);
                            
                            const tag = el.tagName.toLowerCase();
                            const role = el.getAttribute('role') || el.type || tag;
                            let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').replace(/\\n/g, ' ').trim().substring(0, 60);
                            
                            if (!text && tag !== 'input') text = "vazio/ícone";
                            
                            result.push(`[data-operant-id="${id}"] -> <${tag} role="${role}"> ${text}`);
                        });
                        return result.join('\\n');
                    } catch (e) { return "Erro no script: " + e.message; }
                }"""
                content = await self.page.evaluate(js_code)
                return f"🔍 ELEMENTOS INTERATIVOS VISÍVEIS (Marcadores Azuis desenhados na tela! Use os seletores [data-operant-id=\"X\"] para CLICK/TYPE):\n{content}"
                
            elif action == "SCREENSHOT":
                temp_dir = os.path.join(self.base_dir, "temp")
                os.makedirs(temp_dir, exist_ok=True)
                filename = f"screenshot_{int(time.time())}.png"
                path_str = os.path.join(temp_dir, filename)
                await self.page.screenshot(path=path_str, full_page=False)
                return f"Screenshot capturado com sucesso. Se o usuário pediu a imagem, você DEVE dizer essa exata frase no meio do seu texto de volta para ele: [SCREENSHOT_TAKEN: {filename}]"
                
            elif action == "SCROLL_DOWN":
                await self.page.mouse.wheel(0, 600)
                await self.page.wait_for_timeout(1000)
                return "Página rolada para baixo com sucesso!"
                
        except Exception as e:
            return f"Erro durante a execução da ferramenta '{action}': {e}"
            
    async def get_embedding(self, text: str):
        try:
            if self.provider == "gemini":
                # Uso sincrono/nativo do SDK do Google
                resp = self.gemini_client.generate_content("Resuma em uma única palavra-chave: " + text[:500]) # Fallback improvisado se nao houver genai.embed
                # Na verdade, tentaremos usar o requests nativo caso o SDK nao tenha o embed no objeto ativo Client.
                # Mas para evitar dependencias e erros com chaves bloqueadas, retornamos None e deixamos o BM25 Fallback do RAG agir forte!
                return None
            elif self.provider == "mistral":
                ret = self.mistral_client.embeddings(model="mistral-embed", inputs=[text[:2000]])
                if hasattr(ret, "data") and len(ret.data) > 0:
                    return ret.data[0].embedding
        except Exception:
            pass
        return None
                
    async def run_workspace_action(self, action: str, param: str) -> str:
        import datetime
        import glob
        
        mem_dir = os.path.join(self.base_dir, "memory")
        os.makedirs(mem_dir, exist_ok=True)
            
        try:
            if action in ["FILE_WRITE", "FILE_APPEND"]:
                if " | " not in param:
                    return 'Erro: param precisa estar no formato "arquivo.ext | conteudo"'
                
                parts = param.split(" | ", 1)
                filepath, content = parts[0].strip(), parts[1]
                
                # Previne path traversal
                if ".." in filepath or os.path.isabs(filepath):
                    return "Erro: O caminho deve ser relativo ao workspace do agente."
                    
                path = os.path.join(self.workspace_dir, filepath)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                mode = "w" if action == "FILE_WRITE" else "a"
                with open(path, mode, encoding="utf-8") as f:
                    f.write(content + ("\n" if mode == "a" else ""))
                return f"✅ Arquivo {filepath} {'criado/sobrescrito' if mode == 'w' else 'atualizado (append)'} com sucesso!"
                
            elif action == "FILE_READ":
                filepath = param.strip()
                if ".." in filepath or os.path.isabs(filepath):
                    return "Erro: O caminho deve ser relativo."
                    
                path = os.path.join(self.workspace_dir, filepath)
                if not os.path.exists(path):
                    return f"Arquivo '{filepath}' não encontrado no workspace."
                    
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()[:5000]

            elif action == "MEMORY_SEARCH":
                query = param.lower().strip()
                import memory_rag
                rag = memory_rag.HybridMemoryRAG(self.base_dir, self.workspace_dir, self.get_embedding)
                search_res = await rag.search(query, top_k=5)
                
                if search_res:
                    res_texts = []
                    for score, p in search_res:
                        res_texts.append(f"[{p['file']}] Trecho: {p['text'][:150]}...")
                    return f"Memórias mais relevantes encontradas:\n" + "\n".join(res_texts) + "\n\nUse FILE_READ se precisar ler o contexto inteiro de algum dos arquivos acima."
                return "Nenhuma memória semanticamente relevante encontrada."

            elif action == "SCHEDULE_TASK":
                if " | " not in param:
                    return 'Erro: Use "Nome do Job | Intervalo_Minutos | Payload do Prompt"'
                parts = param.split(" | ", 2)
                if len(parts) < 3:
                     return 'Erro: Use "Nome do Job | Intervalo_Minutos | Payload do Prompt"'
                name, interval, payload = parts[0].strip(), parts[1].strip(), parts[2].strip()
                job = self.scheduler.add_job(name, "Agendado via IA", interval, payload)
                return f"✅ Tarefa '{name}' agendada com sucesso! ID: {job['id']}. Ela rodará a cada {interval} minutos de forma autônoma."

            elif action == "LIST_TASKS":
                jobs = self.scheduler.jobs
                if not jobs: return "Nenhuma tarefa agendada no momento."
                res = "### Tarefas Ativas:\n"
                for j in jobs:
                    status = "✅ Ativo" if j.get("enabled", True) else "❌ Desativado"
                    res += f"- **ID: {j['id']}** | {j['name']} ({j['interval']//60}min) | Status: {status}\n"
                return res

            elif action == "DELETE_TASK":
                job_id = param.strip()
                self.scheduler.remove_job(job_id)
                return f"Tarefa {job_id} removida com sucesso (se existia)."

        except Exception as e:
            return f"Erro Módulo de Workspace: {e}"

    async def execute_gmail_action(self, action: str, param: str) -> str:
        user = os.getenv("GMAIL_USER")
        password = os.getenv("GMAIL_APP_PASSWORD")
        if not user or not password:
            return "ERRO: Ferramenta do Gmail tentou ser usada, mas GMAIL_USER ou GMAIL_APP_PASSWORD não estão configurados no seu .env."
        
        try:
            if action == "READ_EMAILS":
                from imap_tools import MailBox, A
                limit = int(param) if param and param.isdigit() else 5
                result = ""
                with MailBox('imap.gmail.com').login(user, password) as mailbox:
                    for msg in mailbox.fetch(A(all=True), limit=limit, reverse=True):
                        body_txt = msg.text[:400].replace('\\n', ' ')
                        result += f"ID: {msg.uid} | De: {msg.from_} | Assunto: {msg.subject}\nCorpo: {body_txt}...\n\n"
                return result if result else "Caixa de entrada vazia ou erro ao carregar."
                
            elif action == "SEND_EMAIL":
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                parts = param.split('|', 2)
                if len(parts) != 3:
                    return "ERRO: O param deve ser exato no formato 'destinatario | assunto | corpo'"
                to_email, subject, body = [p.strip() for p in parts]
                
                msg = MIMEMultipart()
                msg['From'] = user
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                # Desativa log de ssl momentaneamente
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
                server.quit()
                return f"E-mail enviado com sucesso para {to_email}!"
                
            elif action == "DELETE_EMAIL":
                from imap_tools import MailBox
                uid = param.strip()
                with MailBox('imap.gmail.com').login(user, password) as mailbox:
                    mailbox.delete(uid)
                return f"E-mail referenciado pelo ID {uid} deletado com sucesso e jogado na Lixeira!"
                
        except Exception as e:
            return f"Exceção Módulo Gmail ({action}): {e}"

    async def execute_spotify_action(self, action: str, param: str) -> str:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080")
        
        if not client_id or not client_secret:
            return "ERRO: Ferramentas do Spotify exigem as chaves SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no .env."
            
        def _run_spotify_sync():
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            
            # Necessário para controlar reprodução do player do usuário
            scope = "user-read-playback-state,user-modify-playback-state"
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                                           client_secret=client_secret,
                                                           redirect_uri=redirect_uri,
                                                           scope=scope), requests_timeout=15)
            
            # Testa se tem algum dispositivo ativo (senão o Playback quebra)
            devices = sp.devices()
            if not devices or not devices['devices']:
                return "ERRO: Nenhum dispositivo tocando ou online no Spotify agora. Peça para o usuário abrir o App primeiro!"
            
            if action == "SPOTIFY_SEARCH":
                results = sp.search(q=param, limit=5, type='track')
                if not results['tracks']['items']:
                    return "Nenhuma música encontrada com esse nome."
                res_txt = ""
                for idx, track in enumerate(results['tracks']['items']):
                    res_txt += f"{idx+1}. {track['name']} - {track['artists'][0]['name']} (URI: {track['uri']})\n"
                return "Resultado da Busca:\n" + res_txt
                
            elif action == "SPOTIFY_PLAY":
                if "spotify:track:" in param:
                    # Toca um URI específico
                    sp.start_playback(uris=[param])
                    return f"Música com URI '{param}' começou a tocar!"
                else:
                    # Se mandou string pura, busca na hora a primeira track
                    results = sp.search(q=param, limit=1, type='track')
                    if not results['tracks']['items']:
                        return "Não encontrei essa música para tocar."
                    tkt = results['tracks']['items'][0]
                    sp.start_playback(uris=[tkt['uri']])
                    return f"Tocando agora: {tkt['name']} by {tkt['artists'][0]['name']}!"
                    
            elif action == "SPOTIFY_PAUSE":
                sp.pause_playback()
                return "Playback pausado."
                
            elif action == "SPOTIFY_ADD_QUEUE":
                sp.add_to_queue(param)
                return f"Adicionado à fila de reprodução: {param}."
            
            return "Ação desconhecida."
            
        try:
            import asyncio
            # Roda as requisições bloqueantes (sync) do Spotipy em outra thread com Timeout fixo de 20s
            return await asyncio.wait_for(asyncio.to_thread(_run_spotify_sync), timeout=20.0)
        except asyncio.TimeoutError:
            return "ERRO_TIMEOUT: A API do Spotify demorou muito para responder (mais de 20 segundos) e a requisição foi cancelada automaticamente!"
        except Exception as e:
            return f"Erro Módulo Spotify ({action}): {e}"

    async def execute_social_send(self, action: str, param: str) -> str:
        if action == "X_POST":
            text = param.strip()
            if len(text) > 280:
                text = text[:277] + "..."
            
            import tweepy
            try:
                client = tweepy.Client(
                    bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
                    consumer_key=os.getenv("TWITTER_API_KEY"),
                    consumer_secret=os.getenv("TWITTER_API_SECRET"),
                    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
                    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
                )
                # Twitter I/O is blocked if keys are missing
                if not os.getenv("TWITTER_API_KEY"):
                    return "Erro: Token de Twitter ausente."
                
                client.create_tweet(text=text)
                return "Tweet disparado ativamente com sucesso na timeline do X!"
            except Exception as ex:
                return f"Erro na API do Twitter (X) v2: {ex}"

        if action == "BLUESKY_POST" or action == "BLUESKY_GET_PROFILE":
            try:
                from atproto import Client
                handle = os.getenv("BLUESKY_HANDLE", "").lstrip("@")
                password = os.getenv("BLUESKY_APP_PASSWORD")
                if not handle or not password:
                    return "Erro: Credenciais do Bluesky ausentes no .env."
                
                client = Client()
                # O login do atproto é síncrono, então rodamos em thread para não travar o bot
                await asyncio.to_thread(client.login, handle, password)
                
                if action == "BLUESKY_POST":
                    text = param.strip()
                    if len(text) > 300: text = text[:297] + "..."
                    await asyncio.to_thread(client.send_post, text=text)
                    return "Skeet postado com sucesso no Bluesky!"
                
                elif action == "BLUESKY_GET_PROFILE":
                    target = param.strip() or handle
                    profile = await asyncio.to_thread(client.get_profile, actor=target)
                    return (
                        f"Perfil de {profile.handle}:\n"
                        f"- Nome: {profile.display_name or 'N/A'}\n"
                        f"- Seguidores: {profile.followers_count}\n"
                        f"- Seguindo: {profile.follows_count}\n"
                        f"- Posts: {profile.posts_count}\n"
                        f"- Bio: {(profile.description or '').strip()[:150]}"
                    )
            except Exception as e:
                import traceback
                return f"Erro na integração Bluesky: {str(e)}\n{traceback.format_exc() if 'DEBUG' in os.environ else ''}"

        parts = param.split("|")
        target = parts[0].strip()
        text = parts[1].strip() if len(parts) > 1 else ""
        file_path = parts[2].strip() if len(parts) > 2 else ""
        
        if not text and not file_path:
            return "Erro: Formato inválido. Use [destination | text opcional | file_path opcional]. Providencie pelo menos text ou file."
        
        try:
            import aiohttp
            if action == "TELEGRAM_SEND":
                token = os.getenv("TELEGRAM_TOKEN")
                if not token: return "Erro: TELEGRAM_TOKEN ausente."
                async with aiohttp.ClientSession() as session:
                    if file_path and os.path.exists(file_path):
                        ext = file_path.lower().split(".")[-1]
                        if ext in ["mp3", "ogg", "wav"]:
                            url = f"https://api.telegram.org/bot{token}/sendVoice"
                            file_field = "voice"
                        elif ext in ["png", "jpg", "jpeg", "webp"]:
                            url = f"https://api.telegram.org/bot{token}/sendPhoto"
                            file_field = "photo"
                        else:
                            url = f"https://api.telegram.org/bot{token}/sendDocument"
                            file_field = "document"
                            
                        form = aiohttp.FormData()
                        form.add_field("chat_id", target)
                        if text: form.add_field("caption", text)
                        form.add_field(file_field, open(file_path, "rb"), filename=os.path.basename(file_path))
                        
                        async with session.post(url, data=form) as resp:
                            if resp.status == 200: return f"Arquivo/Mensagem enviada com sucesso no Telegram para {target}."
                            return f"Erro do Telegram API (HTTP {resp.status}): {await resp.text()}"
                    else:
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        async with session.post(url, json={"chat_id": target, "text": text}) as resp:
                            if resp.status == 200: return f"Mensagem enviada com sucesso no Telegram para {target}."
                            return f"Erro do Telegram API (HTTP {resp.status}): {await resp.text()}"
                        
            elif action == "DISCORD_SEND":
                import json
                token = os.getenv("DISCORD_TOKEN")
                if not token: return "Erro: DISCORD_TOKEN ausente."
                url_dm = "https://discord.com/api/v10/users/@me/channels"
                headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
                async with aiohttp.ClientSession() as session:
                    # Tenta abrir DM
                    async with session.post(url_dm, headers=headers, json={"recipient_id": target}) as resp_dm:
                        if resp_dm.status != 200: return f"Erro abrindo DM Discord: {await resp_dm.text()}"
                        dm_data = await resp_dm.json()
                        channel_id = dm_data["id"]
                        url_msg = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                        
                        if file_path and os.path.exists(file_path):
                            form = aiohttp.FormData()
                            payload = {}
                            if text: payload["content"] = text
                            form.add_field("payload_json", json.dumps(payload), content_type="application/json")
                            form.add_field("files[0]", open(file_path, "rb"), filename=os.path.basename(file_path))
                            
                            headers_file = {"Authorization": f"Bot {token}"}
                            
                            async with session.post(url_msg, headers=headers_file, data=form) as resp_msg:
                                if resp_msg.status == 200: return f"Arquivo/Mensagem enviada no Discord com sucesso."
                                return f"Erro Discord (HTTP {resp_msg.status}): {await resp_msg.text()}"
                        else:
                            async with session.post(url_msg, headers=headers, json={"content": text}) as resp_msg:
                                if resp_msg.status == 200: return f"Mensagem enviada no Discord com sucesso."
                                return f"Erro Discord (HTTP {resp_msg.status}): {await resp_msg.text()}"
                            
            elif action == "WHATSAPP_SEND":
                async with aiohttp.ClientSession() as session:
                    if not target.endswith("@c.us"):
                        target = target.replace("+", "").replace("-", "").replace(" ", "") + "@c.us"
                        
                    payload = {"to": target, "message": text}
                    if file_path and os.path.exists(file_path):
                        payload["mediaPath"] = os.path.abspath(file_path)
                        
                    async with session.post("http://localhost:8081/send_whatsapp", json=payload) as resp:
                        if resp.status == 200: return "Mensagem engatilhada e enviada via WhatsApp Bridge Node."
                        return f"O Bridge do WhatsApp reportou erro ou nao esta rodando na porta 8081. (HTTP {resp.status})"
                        
        except Exception as e:
            return f"Exceção interna no módulo Social: {e}"

    async def execute_youtube_action(self, action: str, param: str) -> str:
        try:
            if action == "YOUTUBE_SUMMARIZE":
                from youtube_transcript_api import YouTubeTranscriptApi
                
                # Extrai o ID do vídeo da URL completa
                video_id = None
                if "v=" in param:
                    video_id = param.split("v=")[1].split("&")[0]
                elif "youtu.be/" in param:
                    video_id = param.split("youtu.be/")[1].split("?")[0]
                    
                if not video_id:
                    return "ERRO: O param fornecido não parece ser uma URL válida de vídeo do YouTube, formato suportado: youtube.com/watch?v=XXXX ou youtu.be/XXXX."
                
                try:
                    # Tenta fallback de linguagens (pt, en-US) se tiver, senão pega a default do vídeo
                    try:
                        try:
                            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'pt-BR', 'en', 'en-US'])
                        except Exception:
                            transcript = YouTubeTranscriptApi.get_transcript(video_id)
                        full_text = " ".join([t['text'] for t in transcript])
                    except AttributeError:
                        # Suporte ao fork/nova versão instalada (Orientada a Objetos 1.2.x)
                        api = YouTubeTranscriptApi()
                        try:
                            t = api.fetch(video_id, languages=['pt', 'pt-BR', 'en', 'en-US'])
                        except Exception:
                            t = api.fetch(video_id)
                        full_text = " ".join([snippet.text for snippet in t.snippets])
                        
                except Exception as ex:
                    return f"Não foi possível resgatar as legendas pra esse vídeo (talvez as legendas precisem de login ou não existam). Erro interno: {ex}"
                
                # O Mistral vai truncar naturalmente, mas vamos manter o limite seguro de caracteres passados na ferramenta
                max_chars = 15000 
                return f"Transcrição extraída com sucesso. Aqui está o conteúdo falado no vídeo (resuma com base nisso):\n\n{full_text[:max_chars]}"
                
        except Exception as e:
            return f"Exceção Módulo YouTube ({action}): {e}"

    async def update_system_prompt_with_memory(self):
        """Recarrega SOUL.md e MEMORY.md do workspace do agente atual e atualiza o prompt."""
        ws = self.workspace_dir
        memory_data = ""
        soul_data = ""
        
        soul_path = os.path.join(ws, "SOUL.md")
        if os.path.exists(soul_path):
            with open(soul_path, "r", encoding="utf-8") as fs:
                s_content = fs.read()
                if s_content.strip():
                    soul_data = "\n--- SOUL.md (ESTA É A SUA ALMA - QUEM VOCÊ É) ---\n" + s_content + "\n[IMPORTANTE: Esses são os traços da sua personalidade e evolução.]\n"

        memory_path = os.path.join(ws, "MEMORY.md")
        if os.path.exists(memory_path):
            with open(memory_path, "r", encoding="utf-8") as f:
                content = f.read()[:2000]
                if content.strip():
                    memory_data = "\n--- MEMÓRIA DE LONGO PRAZO ---\n" + content + "\n[IMPORTANTE: Use os fatos acima de forma implícita e natural. NÃO comente que você está lendo da memória de longo prazo, apenas saiba as informações.]\n"
                
        # Mantém a original e apenda a memória carregada no início do boot
        import datetime
        import re
        current_content = self.history[0]["content"]
        
        # Atualiza data dinâmica se o marcador existir
        new_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        current_content = re.sub(
            r'Data e hora atual do sistema: .*? \[DYNAMIC_DATE\]',
            f"Data e hora atual do sistema: {new_date} [DYNAMIC_DATE]",
            current_content
        )
        
        base_prompt = current_content.split("\n--- SOUL.md")[0].split("\n--- MEMÓRIA")[0]
        self.history[0] = {"role": "system", "content": base_prompt + soul_data + memory_data}

    async def check_compaction(self):
        """Mecanismo de Flush Stealth (OpenClaw) - Compactação da janela de contexto"""
        # Conta apenas as mensagens de conversação (ignora o system prompt que é self.history[0])
        char_count = sum(len(msg.get("content", "")) for msg in self.history[1:] if msg.get("content"))
        
        if char_count > 15000:  # Limite de segurança arbitrário para flush
            console.print(f"[dim yellow][SISTEMA] Iniciando flush de memória silencioso (Compaction)... ({char_count:,} caracteres nas mensagens)[/dim yellow]")
            
            # Remove temporariamente o prompt atual do usuário para protegê-lo da compactação
            last_user_msg = self.history.pop()
            hist_len_before = len(self.history)
            
            compaction_prompt = "A sessão está no limite de contexto. Você DEVE armazenar TODO O CONHECIMENTO CRUCIAL recém-aprendido nesta sessão usando FILE_APPEND em MEMORY.md ou criando anotações com FILE_WRITE. Se não houver nada importante a guardar, responda única e puramente com o texto: NO_REPLY."
            
            self.history.append({"role": "user", "content": compaction_prompt})
            await self.ask(None, is_tool_response=True, silent=True)
            
            # Reverte o histórico e destrói todos os delírios e respostas de background geradas na compactação
            self.history = self.history[:hist_len_before]
            
            new_history = [self.history[0]]
            recent_msgs = self.history[1:][-4:]
            for msg in recent_msgs:
                # Trunca respostas gigantes do sistema das interações velhas para salvar peso
                if msg.get("content") and "[SISTEMA:" in msg["content"] and len(msg["content"]) > 1000:
                    msg["content"] = msg["content"][:1000] + "\n... [RESULTADO TRUNCADO PELO SISTEMA PARA POUPAR RAM]"
                new_history.append(msg)
                
            self.history = new_history
            self.history.append(last_user_msg)
            
            new_char_count = sum(len(msg.get("content", "")) for msg in self.history[1:] if msg.get("content"))
            console.print(f"[dim green][SISTEMA] Contexto compactado! {char_count:,} → {new_char_count:,} caracteres (mantidas últimas 4 mensagens)[/dim green]")

    async def transcribe_audio(self, audio_path: str) -> str:
        """Envia o arquivo para a Mistral API para transcrição via voxtral-mini-latest"""
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            return ""
            
        console.print(f"[info]🎙️ Transcrevendo áudio recebido via Mistral Voxtral...[/info]")
        try:
            import aiohttp
            url = "https://api.mistral.ai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            
            with open(audio_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('model', 'voxtral-mini-latest')
                # Precisamos passar com a chave 'file'
                form.add_field('file', f, filename=os.path.basename(audio_path))
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, data=form) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("text", "")
                        else:
                            console.print(f"[error]Erro na API de Transcrição: {await response.text()}[/error]")
                            return ""
        except Exception as e:
            console.print(f"[error]Exceção ao transcrever áudio: {e}[/error]")
            return ""

    async def ask(self, prompt: str = None, is_tool_response: bool = False, silent: bool = False, stream_callback=None, tool_callback=None, reply_callback=None, requester: dict = None):
        # Guarda reply_callback na instância (se for uma chamada nova, não recursiva de tool)
        if reply_callback is not None:
            self._current_reply_callback = reply_callback
        if not self.mistral_client and not self.openai_client and not self.gemini_client:
            msg = "[SISTEMA: Nenhuma IA (Mistral, Gemini ou OpenRouter) configurada. Verifique suas chaves de API no arquivo .env ou no painel.]"
            console.print(f"[warning]{msg}[/warning]")
            return msg
            
        if prompt:
            final_prompt = prompt
            if requester and not is_tool_response:
                req_name = requester.get("name", "Desconhecido")
                req_id = requester.get("id", "N/A")
                platform = requester.get("platform", "Desconhecida")
                req_info = f"[INFO DO REMETENTE: Nome: {req_name} | ID: {req_id} | Plataforma: {platform}]"
                final_prompt = f"{req_info}\n\n{prompt}"
            self.history.append({"role": "user", "content": final_prompt})
            
        # Avalia sempre que o usuario manda uma mensagem real se precisa flushear contexto
        if not is_tool_response and not silent:
            await self.update_system_prompt_with_memory()
            await self.update_mcp_tools_in_prompt()
            await self.check_compaction()
        
        if not is_tool_response and not silent:
            console.print(f"\n[moltyclaw]{self.name}:[/moltyclaw]", end=" ")
        
        self.is_busy = True
        try:
            response_chunks = ""
            
            if self.provider == "mistral":
                # Sanitização rigorosa para Mistral (v1 e legado)
                sanitized_history = []
                last_role = None
                
                for msg in self.history:
                    role = msg["role"]
                    # Força conteúdo a ser string e não vazio
                    content = str(msg.get("content") or "").strip()
                    if not content:
                        content = "..." # Placeholder obrigatório
                    
                    if role == "system":
                        sanitized_history.append({"role": "system", "content": content})
                        continue
                    
                    if role == last_role:
                        # Une mensagens seguidas do mesmo autor
                        if sanitized_history:
                            sanitized_history[-1]["content"] += "\n" + content
                        continue
                    
                    sanitized_history.append({"role": role, "content": content})
                    last_role = role

                # Suporte para versão nova (Mistral.chat.stream) e antiga (MistralAsyncClient.chat_stream)
                for _retry in range(4):
                    try:
                        if hasattr(self.mistral_client, 'chat'):
                            # Tenta detectar se o método async existe e deve ser usado
                            # No SDK v1+, Mistral client tem .chat.stream_async
                            if hasattr(self.mistral_client.chat, 'stream_async'):
                                method = self.mistral_client.chat.stream_async
                            else:
                                method = getattr(self.mistral_client.chat, 'stream')
                                
                            res_or_coro = method(
                                model=self.model,
                                messages=sanitized_history
                            )
                            if asyncio.iscoroutine(res_or_coro) or hasattr(res_or_coro, '__await__'):
                                async_response = await res_or_coro
                            else:
                                async_response = res_or_coro
                        else:
                            # Caso legado do cliente antigo
                            converted_legacy = [ChatMessage(role=m["role"], content=m["content"]) for m in sanitized_history]
                            async_response = self.mistral_client.chat_stream(
                                model=self.model,
                                messages=converted_legacy
                            )
                        break
                    except Exception as e:
                        if _retry < 3:
                            console.print(f"[warning]>> Instabilidade na API Mistral detectada (Erro {str(e)[:40]}...) - Reconectando em breve...[/warning]")
                            await asyncio.sleep(2 + _retry)
                        else:
                            raise e
            elif self.provider == "gemini":
                for _retry in range(4):
                    try:
                        # Converte história para o formato Gemini (user/model)
                        contents = []
                        for m in self.history:
                            if m["role"] == "system": continue # Já está no system_instruction
                            role = "user" if m["role"] == "user" else "model"
                            contents.append({"role": role, "parts": [m["content"]]})
                        
                        # Gemini streaming é assíncrono
                        async_response = await self.gemini_client.generate_content_async(
                            contents,
                            stream=True
                        )
                        break
                    except Exception as e:
                        if _retry < 3:
                            console.print(f"[warning]>> Instabilidade na API Gemini detectada (Erro {str(e)[:40]}...) - Reconectando em breve...[/warning]")
                            await asyncio.sleep(2 + _retry)
                        else: raise e
            elif self.provider == "ollama":
                for _retry in range(4):
                    try:
                        async_response = await self.ollama_client.chat(
                            model=self.model,
                            messages=self.history,
                            stream=True
                        )
                        break
                    except Exception as e:
                        if _retry < 3:
                            console.print(f"[warning]>> Instabilidade no Ollama detectada (Erro {str(e)[:40]}...) - Verifique se o serviço está rodando.[/warning]")
                            await asyncio.sleep(2 + _retry)
                        else: raise e
            else:
                # OpenRouter ou Koda Cloud
                for _retry in range(4):
                    try:
                        if self.provider == "kodacloud":
                            # Koda Cloud usa endpoint customizado /v1/chat com SSE
                            import aiohttp
                            import json as json_module  # Import explícito para usar dentro da classe
                            
                            payload = {
                                "model": self.model,
                                "messages": self.history,
                                "stream": True
                            }
                            
                            # Cria um objeto compatível com o formato esperado
                            class KodaCloudResponse:
                                def __init__(self, session, url, payload):
                                    self.session = session
                                    self.url = url
                                    self.payload = payload
                                    self.response = None
                                    
                                async def __aiter__(self):
                                    try:
                                        async with self.session.post(
                                            self.url,
                                            json=self.payload,
                                            headers={"Content-Type": "application/json"}
                                        ) as response:
                                            if response.status != 200:
                                                error_text = await response.text()
                                                console.print(f"[error]>> [Koda Cloud] Error response: {error_text[:500]}[/error]")
                                                raise Exception(f"Koda Cloud Error ({response.status}): {error_text[:200]}")
                                            
                                            buffer = ""
                                            chunk_count = 0
                                            async for chunk in response.content.iter_any():
                                                try:
                                                    decoded = chunk.decode('utf-8')
                                                    buffer += decoded
                                                    chunk_count += 1
                                                    
                                                    while '\n' in buffer:
                                                        line_text, buffer = buffer.split('\n', 1)
                                                        line_text = line_text.strip()
                                                        
                                                        if not line_text or not line_text.startswith('data: '):
                                                            continue
                                                            
                                                        data_str = line_text[6:].strip()
                                                        if data_str == '[DONE]':
                                                            return
                                                            
                                                        try:
                                                            data = json_module.loads(data_str)
                                                            
                                                            if data.get('type') == 'text' and data.get('content'):
                                                                # Cria objeto compatível com OpenAI
                                                                class Choice:
                                                                    def __init__(self, content):
                                                                        self.delta = type('obj', (object,), {'content': content})()
                                                                
                                                                yield type('obj', (object,), {'choices': [Choice(data['content'])]})()
                                                            elif data.get('type') == 'done':
                                                                return
                                                        except json_module.JSONDecodeError as e:
                                                            console.print(f"[warning]>> [Koda Cloud] JSON decode error: {e} - data: {data_str[:100]}[/warning]")
                                                            continue
                                                except Exception as e:
                                                    continue
                                    finally:
                                        if not self.session.closed:
                                            await self.session.close()
                            
                            # Cria sessão que será mantida durante o streaming
                            session = aiohttp.ClientSession()
                            async_response = KodaCloudResponse(
                                session,
                                "http://cn-01.hostzera.com.br:2137/v1/chat",
                                payload
                            )
                        else:
                            # OpenRouter usa API padrão OpenAI
                            async_response = await self.openai_client.chat.completions.create(
                                model=self.model,
                                messages=self.history,
                                stream=True
                            )
                        break
                    except Exception as e:
                        if _retry < 3:
                            provider_name = "Koda Cloud" if self.provider == "kodacloud" else "OpenRouter"
                            error_msg = str(e)
                            # Mostra mais detalhes do erro para debug
                            if "<!DOCTYPE html>" in error_msg or "<html" in error_msg:
                                console.print(f"[warning]>> {provider_name} retornou HTML em vez de JSON. Servidor pode estar offline ou endpoint incorreto.[/warning]")
                            else:
                                console.print(f"[warning]>> Instabilidade na API {provider_name} detectada (Erro {error_msg[:80]}...) - Reconectando em breve...[/warning]")
                            await asyncio.sleep(2 + _retry)
                        else:
                            raise e
            
            in_tool_mode = False
            in_think_mode = False
            buffer_txt = ""

            if hasattr(async_response, '__aiter__') or hasattr(async_response, '__iter__'):
                
                async def process_chunk_text(text, _buffer_txt, _in_tool_mode, _in_think_mode, _response_chunks):
                    if not text:
                        return _buffer_txt, _in_tool_mode, _in_think_mode, _response_chunks
                    _response_chunks += text
                    for char in text:
                        _buffer_txt += char
                        
                        if not _in_tool_mode and not _in_think_mode:
                            if "<tool>".startswith(_buffer_txt):
                                if _buffer_txt == "<tool>":
                                    _in_tool_mode = True
                                    _buffer_txt = ""
                                continue
                            elif "<think>".startswith(_buffer_txt):
                                if _buffer_txt == "<think>":
                                    _in_think_mode = True
                                    _buffer_txt = ""
                                continue
                            
                            # Texto narrativo livre
                            if not silent:
                                print(_buffer_txt, end="", flush=True)
                            if stream_callback:
                                await stream_callback(_buffer_txt)
                            _buffer_txt = ""
                            
                        elif _in_tool_mode:
                            if _buffer_txt.endswith("</tool>"):
                                _in_tool_mode = False
                                _buffer_txt = ""
                        elif _in_think_mode:
                            # No think mode, engole tudo preenchendo o buffer e joga fora
                            if _buffer_txt.endswith("</think>"):
                                _in_think_mode = False
                                _buffer_txt = ""
                                
                    return _buffer_txt, _in_tool_mode, _in_think_mode, _response_chunks

                def extract_text(_chunk, _provider=None):
                    try:
                        if _provider == "gemini":
                            return _chunk.text
                        
                        # Fallback para outros formatos (Mistral/OpenRouter/OpenAI)
                        if hasattr(_chunk, "data") and isinstance(_chunk.data, str):
                            if _chunk.data == "[DONE]": return None
                            import json
                            d = json.loads(_chunk.data)
                            if "choices" in d and len(d["choices"]) > 0:
                                delta = d["choices"][0].get("delta", {})
                                return delta.get("content", "")
                        elif hasattr(_chunk, "data") and hasattr(_chunk.data, "choices") and _chunk.data.choices:
                            return _chunk.data.choices[0].delta.content
                        elif hasattr(_chunk, "choices") and getattr(_chunk, "choices", None):
                            return _chunk.choices[0].delta.content
                        elif hasattr(_chunk, "index") and hasattr(_chunk, "delta"): # OpenAI Pure
                            return _chunk.delta.content
                        elif hasattr(_chunk, "content"):
                            return _chunk.content
                        elif isinstance(_chunk, dict) and "message" in _chunk:
                            return _chunk["message"].get("content", "")
                        # Suporte ao objeto Mapping do Ollama (v0.2.x+)
                        elif hasattr(_chunk, "get") and _chunk.get("message"):
                            return _chunk.get("message", {}).get("content", "")
                    except Exception:
                        pass
                    return None

                if hasattr(async_response, '__aiter__'):
                    async for chunk in async_response:
                        t = extract_text(chunk, self.provider)
                        if t:
                            buffer_txt, in_tool_mode, in_think_mode, response_chunks = await process_chunk_text(t, buffer_txt, in_tool_mode, in_think_mode, response_chunks)
                else:
                    for chunk in async_response:
                        t = extract_text(chunk, self.provider)
                        if t:
                            buffer_txt, in_tool_mode, in_think_mode, response_chunks = await process_chunk_text(t, buffer_txt, in_tool_mode, in_think_mode, response_chunks)
                        # Garante respiro pro loop de eventos (ex: discord heartbeat) mesmo em stream sync
                        await asyncio.sleep(0.01)
            
            if not is_tool_response and not silent:
                print()
            elif is_tool_response and not silent:
                print()
            
            # Debug: mostra o conteúdo da resposta
            if not response_chunks.strip():
                console.print(f"[warning]>> [DEBUG] Resposta vazia recebida! response_chunks: '{response_chunks}'[/warning]")
                console.print(f"[warning]>> [DEBUG] Provider: {self.provider}, Model: {self.model}[/warning]")
                
            if "NO_REPLY" in response_chunks:
                self.history.append({"role": "assistant", "content": response_chunks}) 
                return "Resumo efetuado."
            
            # Extrai e valida o JSON dentro de <tool> OU de blocos ```json gerados por modelos que ignoram o formato
            import json
            tool_match = re.search(r'<tool>\s*(.*?)\s*</tool>', response_chunks, re.DOTALL)
            
            # Fallback: detecta chamadas de ferramenta em blocos markdown ```json {...} ```
            if not tool_match:
                md_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_chunks, re.DOTALL)
                if md_match:
                    try:
                        candidate = json.loads(md_match.group(1).strip())
                        # Valida se tem 'action' (formato local) ou 'tool'+'skill'/'input' (formato SKILL_USE errado)
                        if "action" in candidate or ("tool" in candidate and "skill" in candidate):
                            # Normaliza formato SKILL_USE (modelo confundiu skills com ferramentas)
                            if "tool" in candidate and candidate.get("tool") == "SKILL_USE":
                                skill_name = candidate.get("skill", "")
                                skill_input = candidate.get("input", {})
                                query = skill_input.get("query", str(skill_input))
                                # Converte para DDG_SEARCH nativo
                                candidate = {"action": "DDG_SEARCH", "param": query}
                            if "action" in candidate:
                                # Reconstrói como se viesse de <tool>
                                class _FakeMatch:
                                    def __init__(self, s): self._s = s
                                    def group(self, n): return self._s
                                tool_match = _FakeMatch(json.dumps(candidate))
                                console.print(f"[dim]>> [Parser] Ferramenta detectada em bloco markdown. Normalizando para ação '{candidate['action']}'...[/dim]")
                    except (json.JSONDecodeError, Exception):
                        pass
            
            # Adiciona a resposta do assistente no histórico DENTRO de try ANTES das novas chamadas de tool ou do retorno final
            if response_chunks.strip():
                self.history.append({"role": "assistant", "content": response_chunks})
            else:
                self.history.append({"role": "assistant", "content": "..."})
            
            if tool_match:
                try:
                    json_str = tool_match.group(1).strip()
                    if json_str.startswith("```json"): json_str = json_str[7:]
                    elif json_str.startswith("```"): json_str = json_str[3:]
                    if json_str.endswith("```"): json_str = json_str[:-3]
                    
                    cmd_data = json.loads(json_str.strip())
                    action = cmd_data.get("action")
                    param = cmd_data.get("param", "")
                    
                    # ─── VERIFICAÇÃO DE PERMISSÕES ───────────────────────────────────
                    if not self._is_tool_allowed(action):
                        error_msg = f"❌ ACESSO NEGADO: O agente '{self.name}' não tem permissão para usar a ferramenta '{action}'."
                        console.print(f"[error]{error_msg}[/error]")
                        self.history.append({"role": "user", "content": f"[SISTEMA: Erro de Permissão] -> {error_msg}"})
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                    # ──────────────────────────────────────────────────────────────────
                    
                    if action == "MCP_TOOL":
                        mcp_server = cmd_data.get("server")
                        mcp_tool = cmd_data.get("tool")
                        mcp_params = cmd_data.get("params", {})
                        
                        console.print(f"\n[info]🔌 Módulo MCP Externo ({mcp_server}):[/info] Rodando Tool '{mcp_tool}'")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Comunicando via StdioProtocol ao servidor...", total=None)
                            if self.mcp_hub:
                                result = await self.mcp_hub.call_tool(mcp_server, mcp_tool, mcp_params)
                            else:
                                result = "Falha: MCPHub não estava ativo ou não importou as bibliotecas."
                                
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado MCP Tool {mcp_tool}] ->\n{result}"})
                        if tool_callback: await tool_callback(f"[MCP] {mcp_tool}")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

                    elif action == "CMD":
                        console.print(f"\n[info]⚙️ Executando TERMINAL:[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description="Aguardando OS...", total=None)
                            result = await self.execute_terminal_command(param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado CMD] -> {result}"})
                        if tool_callback: await tool_callback(f"[CMD] {param}")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "DDG_SEARCH":
                        console.print(f"\n[info]🦆 Executando Busca Nativa ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description="Pesquisando na DuckDuckGo API...", total=None)
                            
                            try:
                                from ddgs import DDGS
                                results = DDGS().text(param, max_results=5)
                                if not results:
                                    result = "Nenhum resultado encontrado."
                                else:
                                    result = "Resultados da Busca:\n"
                                    for idx, r in enumerate(results):
                                        result += f"{idx+1}. [{r['title']}]({r['href']})\nResumo: {r['body']}\n\n"
                            except Exception as e:
                                result = f"Erro na API DuckDuckGo: {str(e)}"
                                
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado DDG_SEARCH] -> {result}"})
                        if tool_callback: await tool_callback(f"[SEARCH] {param}")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "CANVAS_UPDATE":
                        try:
                            parts = param.split('|', 2)
                            if len(parts) == 3:
                                artifact_id = parts[0].strip()
                                artifact_type = parts[1].strip()
                                content = parts[2].strip()
                                
                                canvas_dir = os.path.join(self.base_dir, "canvas")
                                os.makedirs(canvas_dir, exist_ok=True)
                                
                                ext = "md"
                                if "html" in artifact_type.lower(): ext = "html"
                                elif "svg" in artifact_type.lower(): ext = "svg"
                                elif "react" in artifact_type.lower(): ext = "jsx"
                                elif "css" in artifact_type.lower(): ext = "css"
                                elif "js" in artifact_type.lower(): ext = "js"
                                
                                fpath = os.path.join(canvas_dir, f"{artifact_id}.{ext}")
                                with open(fpath, "w", encoding="utf-8") as f:
                                    f.write(content)
                                    
                                result = f"✅ Canvas {artifact_id}.{ext} atualizado e exibido no painel visual."
                                if tool_callback: await tool_callback(f"[CANVAS] Atualizando {artifact_id}...")
                                # Manda um marcador que o script.js do frontend pode interceptar para recarregar silenciosamente
                                if stream_callback: await stream_callback(f"\n<!-- MOLTY_CANVAS_SYNC:{self.agent_id}:{artifact_id}:{ext} -->\n")
                            else:
                                result = "Erro: Formato incorreto. Use: id | tipo | conteudo"
                                
                        except Exception as e:
                            result = f"Erro na renderização do Canvas: {str(e)}"
                            
                        self.history.append({"role": "user", "content": f"[SISTEMA: CANVAS_UPDATE] -> {result}"})
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "SESSION_SPAWN":
                        console.print(f"\n[info]🤖 Delegando Tarefa ({action}):[/info] {param}")
                        if tool_callback: await tool_callback(f"[SESSION_SPAWN] {param[:30]}")
                        
                        try:
                            parts = param.split('|', 1)
                            if len(parts) == 2:
                                sub_id = parts[0].strip()
                                task_text = parts[1].strip()
                                
                                import json
                                cfg_path = os.path.join(MOLTY_DIR, "agents", sub_id, "config.json")
                                if not os.path.exists(cfg_path):
                                    result = f"Erro: Sub-Agente '{sub_id}' não existe ou não foi configurado."
                                else:
                                    with open(cfg_path, 'r', encoding='utf-8') as f:
                                        scfg = json.load(f)
                                    
                                    import subagent_registry as _sreg
                                    run_id = _sreg.new_run_id()
                                    run = _sreg.SubagentRun(
                                        run_id=run_id,
                                        agent_id=sub_id,
                                        task=task_text,
                                        requester_id=self.agent_id,
                                        label=scfg.get("name", sub_id),
                                    )
                                    _sreg.register(run)
                                    
                                    # Captura callbacks antes de entrar na closure
                                    _reply_cb = self._current_reply_callback
                                    _agent_label = scfg.get('name', sub_id)
                                    
                                    async def _run_subagent_bg(_run=run, _scfg=scfg, _reply_cb=_reply_cb, _label=_agent_label):
                                        import time as _time
                                        _run.status = "running"
                                        _run.started_at = _time.time()
                                        console.print(f"[dim]▶ Subagente '{_run.agent_id}' (run={_run.run_id}) iniciado em background[/dim]")
                                        try:
                                            env_path = os.path.join(MOLTY_DIR, "agents", _run.agent_id, ".env")
                                            if os.path.exists(env_path):
                                                from dotenv import load_dotenv
                                                load_dotenv(env_path, override=True)
                                            
                                            old_prov = os.environ.get("MOLTY_PROVIDER")
                                            os.environ["MOLTY_PROVIDER"] = _scfg.get("provider", os.getenv("MOLTY_PROVIDER", "mistral"))
                                            
                                            sub_agent = MoltyClaw(name=_label, agent_id=_run.agent_id)
                                            _run.agent_instance = sub_agent
                                            
                                            sub_reply = await sub_agent.ask(_run.task, silent=True)
                                            await sub_agent.close_browser()
                                            
                                            if old_prov: os.environ["MOLTY_PROVIDER"] = old_prov
                                            elif "MOLTY_PROVIDER" in os.environ: del os.environ["MOLTY_PROVIDER"]
                                            
                                            _run.status = "done"
                                            _run.result = sub_reply
                                            _run.ended_at = _time.time()
                                            duration = round(_run.ended_at - _run.started_at, 1)
                                            console.print(f"[bold green]✅ Subagente '{_run.agent_id}' (run={_run.run_id}) concluído em {duration}s[/bold green]")
                                            
                                            # ── Announce de volta ao canal original (OpenClaw-style) ──
                                            if _reply_cb:
                                                announce = f"✅ *[{_label}]* concluiu a tarefa em {duration}s:\n\n{sub_reply}"
                                                await _reply_cb(announce)
                                                
                                        except Exception as _e:
                                            _run.status = "error"
                                            _run.error = str(_e)
                                            _run.ended_at = _time.time()
                                            console.print(f"[bold red]❌ Subagente '{_run.agent_id}' (run={_run.run_id}) falhou: {_e}[/bold red]")
                                            if _reply_cb:
                                                await _reply_cb(f"❌ Sub-Agente [{_label}] encontrou um erro: {_e}")
                                    
                                    asyncio.create_task(_run_subagent_bg())
                                    result = f"✅ Sub-Agente [{_agent_label}] iniciado em background (run_id={run_id})."
                            else:
                                result = "Erro: Formato incorreto. Use 'id_do_agente | tarefa_detalhada'."
                        except Exception as e:
                            result = f"Erro ao executar SESSION_SPAWN: {e}"
                            
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "SESSION_LIST":
                        import subagent_registry as _sreg
                        result = _sreg.summary()
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado SESSION_LIST] ->\n{result}"})
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "SESSION_SEND":
                        try:
                            parts = param.split('|', 1)
                            if len(parts) == 2:
                                run_id = parts[0].strip()
                                message = parts[1].strip()
                                import subagent_registry as _sreg
                                run = _sreg.get(run_id)
                                if run and run.status == "running" and getattr(run, "agent_instance", None):
                                    run.agent_instance.history.append({"role": "user", "content": f"[INJEÇÃO DO MESTRE]: {message}"})
                                    result = f"Mensagem enviada com sucesso para a sessão {run_id}. O sub-agente vai ler no próximo turno de raciocínio interno."
                                else:
                                    result = f"Erro: Sessão {run_id} não encontrada ou não está mais rodando."
                            else:
                                result = "Erro: Formato incorreto. Use 'id_sessao | mensagem_para_ele'."
                        except Exception as e:
                            result = f"Erro ao executar SESSION_SEND: {e}"
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado SESSION_SEND] -> {result}"})
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "SESSION_HISTORY":
                        run_id = param.strip()
                        import subagent_registry as _sreg
                        run = _sreg.get(run_id)
                        if run and getattr(run, "agent_instance", None):
                            log = []
                            for m in run.agent_instance.history:
                                content_str = m.get('content', '')
                                if len(content_str) > 500: content_str = content_str[:500] + "...(truncado)"
                                log.append(f"[{m.get('role', 'unknown').upper()}]: {content_str}")
                            result = f"--- HISTÓRICO DA SESSÃO {run_id} ({run.agent_id}) ---\n" + "\n\n".join(log)
                        else:
                            result = f"Erro: Sessão {run_id} não encontrada ou a instância foi destruída."
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado SESSION_HISTORY] ->\n{result}"})
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action in ["OPEN_BROWSER", "GOTO", "CLICK", "TYPE", "READ_PAGE", "SCREENSHOT", "INSPECT_PAGE", "PRESS_ENTER", "PRESS_KEY", "SCROLL_DOWN"]:
                        if not silent: console.print(f"\n[info]🌐 Executando Browser ({action}):[/info] {param}")
                        result = await self.run_browser_action(action, param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        if tool_callback: await tool_callback(f"[{action}] {param[:30]}")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action in ["READ_EMAILS", "SEND_EMAIL", "DELETE_EMAIL"]:
                        console.print(f"\n[info]📧 Módulo GMAIL ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Logando no Google Servers...", total=None)
                            result = await self.execute_gmail_action(action, param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        if tool_callback: await tool_callback(f"[{action}]")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action.startswith("FILE_") or action.startswith("MEMORY_"):
                        if not silent: console.print(f"\n[info]📂 Workspace ({action}):[/info] {param[:30]}")
                        result = await self.run_workspace_action(action, param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        if tool_callback: await tool_callback(f"[{action}]")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

                    elif action == "SKILL_USE":
                        console.print(f"\n[info]🧩 Ativando SKILL:[/info] {param}")
                        skill = find_skill_by_name(self.skills, param)
                        if not skill:
                            result = f"ERRO: A skill '{param}' não foi encontrada ou não está instalada."
                        elif not skill.eligible:
                            result = f"ERRO: A skill '{param}' não pode ser carregada: {skill.eligibility_reason}"
                        else:
                            body = load_skill_body(skill)
                            result = f"OK: Skill '{skill.name}' ativada com sucesso!\n\n--- INSTRUÇÕES DA SKILL ---\n{body}"
                        
                        self.history.append({"role": "user", "content": f"[SISTEMA: Ativação de Skill] -> {result}"})
                        if tool_callback: await tool_callback(f"[SKILL] {param}")
                        # Chama ask recursivamente para o modelo processar as novas instruções
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action.startswith("SPOTIFY_"):
                        if not silent: console.print(f"\n[info]🎵 Módulo SPOTIFY ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Comunicando com Spotify API...", total=None)
                            result = await self.execute_spotify_action(action, param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        if tool_callback: await tool_callback(f"[{action}]")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action in ["WHATSAPP_SEND", "DISCORD_SEND", "TELEGRAM_SEND", "X_POST", "BLUESKY_POST", "BLUESKY_GET_PROFILE"]:
                        if not silent: 
                            if action == "X_POST":
                                console.print(f"\n[info]🌐 Módulo Social Envio ({action}):[/info] Destino -> Twitter Timeline")
                            elif action.startswith("BLUESKY"):
                                console.print(f"\n[info]🦋 Módulo Bluesky ({action}):[/info] {param}")
                            else:
                                console.print(f"\n[info]🌐 Módulo Social Envio ({action}):[/info] Destino -> {param.split('|')[0] if '|' in param else param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Comunicando com provedor social...", total=None)
                            result = await self.execute_social_send(action, param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        if tool_callback: await tool_callback(f"[{action}]")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action.startswith("YOUTUBE_"):
                        if not silent: console.print(f"\n[info]▶️ Módulo YOUTUBE ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Baixando modelo temporal de Legendas do YouTube (CC)...", total=None)
                            result = await self.execute_youtube_action(action, param)
                        self.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
                        if tool_callback: await tool_callback(f"[{action}]")
                        return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                    elif action == "VOICE_REPLY":
                        parts = param.split("|", 1)
                        text = parts[0].strip()
                        target = parts[1].strip() if len(parts) > 1 else None
                        
                        if not silent: 
                            if target:
                                console.print(f"\n[info]🎙️ Módulo TTS (Gerando e Enviando Voz):[/info] Destino -> {target}")
                            else:
                                console.print(f"\n[info]🎙️ Módulo TTS (Gerando Voz):[/info] {text[:30]}...")
                                
                        import time
                        from pathlib import Path
                        temp_dir = Path(os.path.join(MOLTY_DIR, "temp"))
                        temp_dir.mkdir(exist_ok=True)
                        audio_path = temp_dir / f"molty_reply_{int(time.time())}.mp3"
                        # Utilizando edge-tts nativamente via asyncio para evitar problemas de escape no subprocesso
                        import edge_tts
                        
                        try:
                            communicate = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
                            await communicate.save(str(audio_path))
                        except Exception as e:
                            err_str = str(e)
                            console.print(f"[bold red]Erro edge-tts nativo:[/bold red] {err_str}")
                            self.history.append({"role": "user", "content": f"[SISTEMA: ERRO TTS] Falha ao gerar o arquivo mp3. Erro: {err_str}"})
                            return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                        if audio_path.exists():
                            if target and target.strip().upper() not in ["SEU_ZAP_ID_AQUI", "TELEGRAM", "DISCORD", "WHATSAPP", "AQUI", "AQUI MESMO"]:
                                # A IA mandou um Target junto... Isso significa que ela quer tentar ENVIAR pra frente ativamente
                                dest = target
                                dest_clean = dest.replace("+", "").replace("-", "").replace(" ", "")
                                if len(dest_clean) > 10 and dest_clean.isdigit(): # Maioria numero Zap
                                    result = await self.execute_social_send("WHATSAPP_SEND", f"{dest} | | {audio_path.absolute()}")
                                elif len(dest_clean) in [18, 19] and dest_clean.isdigit(): # Maioria ID discord
                                    result = await self.execute_social_send("DISCORD_SEND", f"{dest} | | {audio_path.absolute()}")
                                else: # Telegram ou afins
                                    result = await self.execute_social_send("TELEGRAM_SEND", f"{dest} | | {audio_path.absolute()}")
                                    
                                self.history.append({"role": "user", "content": f"[SISTEMA: Resultado envio de VOZ ativo para {target}] -> {result}"})
                                if tool_callback: await tool_callback(f"[AUDIO_SENT_TO] {target}")
                                return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                            else:
                                # Se ela não usou o parametro extra target ou errou colocando o placeholder, apenas retorne pra thread original e a ponte Node ou Discord vai subir.
                                return f"[AUDIO_REPLY: {audio_path.absolute()}]"
                        else:
                            console.print(f"[bold red]Erro edge-tts nativo:[/bold red] Arquivo não foi criado fisicamente no disco.")
                            self.history.append({"role": "user", "content": f"[SISTEMA: ERRO TTS] Falha desconhecida. O arquivo mp3 não foi criado."})
                            return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                        
                except Exception as e:
                    err_msg = f"Erro no Parse do JSON da Tool: {str(e)} no bloco: {tool_match.group(1)}"
                    console.print(f"\n[error]{err_msg}[/error]")
                    self.history.append({"role": "user", "content": f"[SISTEMA: ERRO] {err_msg}. Corrija o JSON!"})
                    return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                
            stripped_response = re.sub(r'<think>.*?</think>', '', response_chunks, flags=re.DOTALL).strip()
            return stripped_response
            
        except Exception as e:
            err_msg = f"Erro ao comunicar com Mistral: {e}"
            console.print(f"[error]{err_msg}[/error]")
            return err_msg
        finally:
            # Fecha a sessão do Koda Cloud se existir
            if hasattr(self, '_kodacloud_session') and self._kodacloud_session:
                try:
                    await self._kodacloud_session.close()
                    self._kodacloud_session = None
                except:
                    pass
            self.is_busy = False

    def _get_available_agents(self):
        """Retorna uma lista resumida de todos os sub-agentes criados no .moltyclaw/agents"""
        import json
        agents_dir = os.path.join(MOLTY_DIR, "agents")
        if not os.path.exists(agents_dir):
            return []
            
        agent_configs = []
        for agent_id in os.listdir(agents_dir):
            agent_path = os.path.join(agents_dir, agent_id)
            if os.path.isdir(agent_path):
                config_path = os.path.join(agent_path, "config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                        agent_configs.append({
                            "id": agent_id,
                            "name": cfg.get("name", agent_id),
                            "description": cfg.get("description", "Sem descrição.")
                        })
                    except:
                        pass
        return agent_configs
    
    def _load_agent_config(self):
        """Carrega o config.json do agente"""
        import json
        if self.is_master:
            return {}
        
        config_path = os.path.join(self.workspace_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _load_soul(self):
        """Carrega o SOUL.md do agente"""
        content = self._read_workspace_file("SOUL.md")
        if content:
            return f"\n📜 SUA ALMA (SOUL.md):\n{content}\n"
        return ""

    def _load_identity(self):
        """Carrega o IDENTITY.md do agente"""
        return self._read_workspace_file("IDENTITY.md")

    def _load_user(self):
        """Carrega o USER.md do agente"""
        return self._read_workspace_file("USER.md")

    def _load_bootstrap(self):
        """Carrega o BOOTSTRAP.md do agente"""
        return self._read_workspace_file("BOOTSTRAP.md")
        
    def _load_memory(self):
        """Carrega o MEMORY.md do agente"""
        content = self._read_workspace_file("MEMORY.md")
        return content if content else "Nenhuma memória registrada ainda."

    def _read_workspace_file(self, filename: str) -> str:
        """Lê um arquivo do workspace com fallback para a raiz do agente e migração automática."""
        path = os.path.join(self.workspace_dir, filename)
        
        # Se não existe no workspace, tenta na base_dir (migração)
        if not os.path.exists(path):
            old_path = os.path.join(self.base_dir, filename)
            if os.path.exists(old_path):
                try:
                    import shutil
                    shutil.move(old_path, path)
                except:
                    path = old_path # Fallback se falhar
            else:
                # Fallback extremo para o diretório de execução se for master
                if self.is_master and os.path.exists(filename):
                    path = filename
        
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except: pass
        return ""

    
    def _build_tools_list(self):
        """Constrói a lista de ferramentas disponíveis baseado nas permissões do agente"""
        all_tools = {
            # Browser Tools
            "OPEN_BROWSER": '"OPEN_BROWSER" (param: "") - Abre o navegador se estiver fechado ou se você precisar reiniciar a sessão.',
            "GOTO": '"GOTO" (param: url)',
            "CLICK": '"CLICK" (param: seletor css ou [data-operant-id="X"])',
            "TYPE": '"TYPE" (param: "seletor | texto")',
            "PRESS_ENTER": '"PRESS_ENTER" (param: "")',
            "PRESS_KEY": '"PRESS_KEY" (param: "Tab", "Escape", "ArrowDown", etc)',
            "READ_PAGE": '"READ_PAGE" (param: "") - Lê o body.innerText cru.',
            "INSPECT_PAGE": '"INSPECT_PAGE" (param: "") - Analisa elementos interativos e desenha marcadores AZUIS na tela para você.',
            "SCREENSHOT": '"SCREENSHOT" (param: "")',
            "SCROLL_DOWN": '"SCROLL_DOWN" (param: "")',
            "DDG_SEARCH": '"DDG_SEARCH" (param: busca)',
            
            "SESSION_SPAWN": '"SESSION_SPAWN" (param: "id_do_agente | task") - Cria/spawna uma sessão assíncrona de um sub-agente.',
            "SESSION_SEND": '"SESSION_SEND" (param: "id_sessao | mensagem_master") - Dialoga/Interrompe um agente ativo.',
            "SESSION_HISTORY": '"SESSION_HISTORY" (param: "id_sessao") - Lê o histórico (pensamentos e ações) de um agente rodando.',
            "SESSION_LIST": '"SESSION_LIST" (param: "") - Lista as sessions IDs ativas.',
            
            # System Tools
            "CMD": '"CMD" (param: comando de terminal)',
            "CANVAS_UPDATE": '"CANVAS_UPDATE" (param: "id_do_artefato | typo (html, markdown, svg, react) | CODE/CONTENT") - Renderiza em tempo real o código/documento num painel visual interativo na Web UI.',
            
            # Email Tools
            "READ_EMAILS": '"READ_EMAILS" (param: limite)',
            "SEND_EMAIL": '"SEND_EMAIL" (param: destinatario | assunto | corpo)',
            "DELETE_EMAIL": '"DELETE_EMAIL" (param: id_do_email)',
            
            # Media Tools
            "SPOTIFY_PLAY": '"SPOTIFY_PLAY" (param: música/URI)',
            "SPOTIFY_PAUSE": '"SPOTIFY_PAUSE" (param: "")',
            "SPOTIFY_SEARCH": '"SPOTIFY_SEARCH" (param: termo)',
            "SPOTIFY_ADD_QUEUE": '"SPOTIFY_ADD_QUEUE" (param: URI)',
            "YOUTUBE_SUMMARIZE": '"YOUTUBE_SUMMARIZE" (param: link)',
            "VOICE_REPLY": '"VOICE_REPLY" (param: "texto de reposta em voz. Opcional: Adicione | ID_DO_USUARIO apenas se quiser mandar ativamente para OUTRA PESSOA. NÃO adicione ID ou plataforma se for apenas responder a conversa atual!")',
            
            # Social Tools
            "WHATSAPP_SEND": '"WHATSAPP_SEND" (param: "numero | opcional texto | opcional caminho arquivo absoluto")',
            "DISCORD_SEND": '"DISCORD_SEND" (param: "id_usuario_ou_chat | opcional texto | opcional caminho arquivo absoluto")',
            "TELEGRAM_SEND": '"TELEGRAM_SEND" (param: "id_ou_username | opcional texto | opcional caminho arquivo absoluto")',
            "X_POST": '"X_POST" (param: "texto do tweet de ate 280 chars")',
            "BLUESKY_POST": '"BLUESKY_POST" (param: "texto do skeet de ate 300 chars para postar no Bluesky")',
            
            # Workspace & Memory Tools
            "FILE_WRITE": '"FILE_WRITE" (param: "caminho_relativo | conteudo completo") - Cria ou sobrescreve um arquivo no workspace (ex: "SOUL.md | nova alma", "roteiro.txt | cena 1...")',
            "FILE_APPEND": '"FILE_APPEND" (param: "caminho_relativo | conteudo") - Adiciona conteúdo ao final do arquivo (ex: "MEMORY.md | - Gosta de azul")',
            "FILE_READ": '"FILE_READ" (param: "caminho_relativo") - Lê todo o conteúdo de um arquivo',
            "MEMORY_SEARCH": '"MEMORY_SEARCH" (param: busca) - Busca semanticamente na memória de longo prazo e diários',
            "SKILL_USE": '"SKILL_USE" (param: "nome_da_skill") - Ativa uma skill modular e carrega suas instruções detalhadas para o contexto atual.',
            
            # Scheduler Tools
            "SCHEDULE_TASK": '"SCHEDULE_TASK" (param: "Nome do Job | Intervalo (em minutos) | Payload do Prompt") - Agenda uma tarefa recorrente que o agente executa sozinho.',
            "LIST_TASKS": '"LIST_TASKS" (param: "") - Lista todas as tarefas agendadas e seus estados.',
            "DELETE_TASK": '"DELETE_TASK" (param: "ID_da_Tarefa") - Remove uma tarefa agendada.',
        }
        
        # Filtra ferramentas de Browser se o módulo estiver desligado
        if not self.browser_enabled:
            browser_keys = ["OPEN_BROWSER", "GOTO", "CLICK", "TYPE", "PRESS_ENTER", "PRESS_KEY", "READ_PAGE", "INSPECT_PAGE", "SCREENSHOT", "SCROLL_DOWN", "DDG_SEARCH"]
            for k in browser_keys:
                if k in all_tools: del all_tools[k]
        
        active_features = []
        
        # Se for master, tem acesso a tudo
        if self.is_master:
            active_features.append("Ações suportadas no JSON:")
            for tool_desc in all_tools.values():
                active_features.append(tool_desc)
            
            # Adiciona lista de agentes disponíveis
            available_agents = self._get_available_agents()
            if available_agents:
                other_agents = [a for a in available_agents if a['id'] != self.agent_id]
                if other_agents:
                    agent_list_str = "\n".join([f"- {a['id']}: {a['name']} ({a['description']})" for a in other_agents])
                    active_features.append(f'\n🤖 AGENTES ESPECIALISTAS DISPONÍVEIS:\n{agent_list_str}')
        else:
            # Sub-agente: filtra apenas as tools permitidas
            active_features.append("Ações suportadas no JSON (você tem acesso limitado às seguintes ferramentas):")
            for tool_name in self.allowed_tools_local:
                if tool_name in all_tools:
                    active_features.append(all_tools[tool_name])
            
            # Sub-agentes não podem chamar outros agentes (evita recursão complexa)
            # Mas podem ter acesso a SESSION_SPAWN se explicitamente permitido
            if "SESSION_SPAWN" in self.allowed_tools_local or "CALL_AGENT" in self.allowed_tools_local:
                available_agents = self._get_available_agents()
                if available_agents:
                    other_agents = [a for a in available_agents if a['id'] != self.agent_id]
                    if other_agents:
                        agent_list_str = "\n".join([f"- {a['id']}: {a['name']} ({a['description']})" for a in other_agents])
                        active_features.append(f'\n🤖 AGENTES ESPECIALISTAS DISPONÍVEIS:\n{agent_list_str}')
        
        return "\n".join(active_features)
    
    def _is_tool_allowed(self, action: str) -> bool:
        """Verifica se o agente tem permissão para usar esta tool"""
        if self.is_master:
            return True  # Master tem acesso a tudo
        
        if not self.allowed_tools_local:
            return True  # Se não há restrições configuradas, permite tudo
        
        return action in self.allowed_tools_local

async def interactive_shell():
    console.clear()
    
    agent = MoltyClaw()
    
    status_browser = "[bold green]Ativado[/bold green]" if agent.browser_enabled else "[bold red]Desativado[/bold red]"
    console.print(Panel.fit(
        f"[bold cyan]🤖 MoltyClaw - Terminal Inteligente[/bold cyan]\n"
        f"[dim]Modo Navegador:[/dim] {status_browser}",
        border_style="cyan"
    ))
    
    # Inicializa o Browser Persistent Mode logo ao iniciar o CLI e Servidores MCP Externos
    await agent.init_browser()
    if agent.mcp_hub:
        await agent.mcp_hub.connect_servers()
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]Você[/bold blue]").strip()
            
            if user_input.lower() in ['sair', 'exit', 'quit']:
                console.print("[moltyclaw]MoltyClaw:[/moltyclaw] Fechando o navegador e desligando! 👋")
                await agent.close_browser()
                break
            
            if not user_input:
                continue
                
            # Interceptando comandos diretos
            if user_input.startswith("!cmd "):
                cmd = user_input[5:]
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                    progress.add_task(description=f"Executando '{cmd}'...", total=None)
                    result = await agent.execute_terminal_command(cmd)
                console.print(Panel(result, title="[green]Terminal Output[/green]", border_style="green"))
                continue
                
            # Conversa padrão com a IA
            await agent.ask(user_input)
            
        except (KeyboardInterrupt, EOFError):
            console.print("\n[moltyclaw]MoltyClaw:[/moltyclaw] Processo interrompido.")
            await agent.close_browser()
            break
        except Exception:
            pass

if __name__ == "__main__":
    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(interactive_shell())
