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

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.theme import Theme

# Módulos refatorados
from browser import BrowserEngine
from providers import resolve_provider_and_key, resolve_model, initialize_clients
from llm_stream import stream_llm
from tool_executor import ToolExecutor
from tool_parser import parse_llm_tool_call
from integrations.gmail import execute_gmail_action
from integrations.spotify import execute_spotify_action
from integrations.youtube import execute_youtube_action

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
        self.console = console
        self.name = name
        self.agent_id = agent_id if agent_id else (name.replace(" (WebUI Gateway)", "").replace(" (Discord)", "").replace(" (Telegram)", "").replace(" (WhatsApp)", "").replace(" (Twitter)", "").replace(" (Bluesky)", "").strip())
        if self.agent_id.startswith("MoltyClaw"):
            self.agent_id = "MoltyClaw"
        self.is_master = (self.agent_id == "MoltyClaw")

        # Detecta o canal pelo nome se não informado explicitamente
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

        self.config = self._load_agent_config()
        self.allowed_tools_local = set(self.config.get("tools_local", [])) if not self.is_master else None
        self.allowed_tools_mcp = set(self.config.get("tools_mcp", [])) if not self.is_master else None

        if not self.is_master:
            agent_env = os.path.join(self.base_dir, ".env")
            if os.path.exists(agent_env):
                console.print(f"[dim]>> Carregando configurações específicas do agente em {agent_env}[/dim]")
                load_dotenv(agent_env, override=True)

        preferred_provider = self.config.get("provider", os.getenv("MOLTY_PROVIDER", "mistral"))
        self.provider, self.api_key, p_cfg = resolve_provider_and_key(preferred_provider, self.name, console=console)
        self.model = resolve_model(self.provider, p_cfg)

        if self.is_master:
            console.print(f"[dim]>> [{self.name}] Provider inicializado: {self.provider}[/dim]")
            console.print(f"[dim]>> [{self.name}] Modelo carregado: {self.model}[/dim]")

        # Browser Engine
        molty_config = get_config()
        self.browser_enabled = molty_config.get("browser", {}).get("enabled", True)
        self.browser_headless = molty_config.get("browser", {}).get("headless", True)
        self.browser = BrowserEngine(
            agent_name=self.name,
            base_dir=self.base_dir,
            browser_enabled=self.browser_enabled,
            browser_headless=self.browser_headless,
            console=console
        )

        self._current_reply_callback = None

        if MCPHub:
            if self.is_master:
                self.mcp_hub = MCPHub()
            else:
                self.mcp_hub = MCPHub(allowed_servers=self.allowed_tools_mcp)
        else:
            self.mcp_hub = None

        active_features = self._build_tools_list()

        soul_content = self._load_soul()
        identity_content = self._load_identity()
        user_content = self._load_user()
        bootstrap_content = self._load_bootstrap()
        memory_content = self._load_memory()

        self.skills = load_skill_entries(self.workspace_dir)
        skills_prompt = build_skills_metadata_prompt(self.skills)

        system_instruction = build_system_prompt(
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
        )

        self.history = [{"role": "system", "content": system_instruction}]

        # Inicialização dos clientes de LLM
        clients = initialize_clients(
            provider=self.provider,
            model=self.model,
            api_key=self.api_key,
            system_instruction=system_instruction,
            agent_name=self.name,
            console=console
        )
        self.mistral_client = clients.mistral_client
        self.openai_client = clients.openai_client
        self.gemini_client = clients.gemini_client
        self.ollama_client = clients.ollama_client
        self.kodacloud_endpoint = clients.kodacloud_endpoint

        # Executor de Ferramentas
        self.tool_executor = ToolExecutor(self)

        self.is_busy = False
        self.pty_bridge_process = None
        self.pty_output = ""

        self.scheduler = SchedulerManager(self, base_dir=self.base_dir)
        self.heartbeat = HeartbeatManager(self)  # type: ignore[arg-type]

    # Propriedades para compatibilidade com código que acessa atributos do browser diretamente
    @property
    def page(self):
        return self.browser.page

    @property
    def context(self):
        return self.browser.context

    @property
    def playwright(self):
        return self.browser.playwright

    def _get_mcp_prompt_placeholder(self) -> str:
        return "[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]"

    async def update_mcp_tools_in_prompt(self):
        if not self.mcp_hub:
            return

        tools_str = await self.mcp_hub.get_all_tools_formatted()
        if not tools_str:
            return

        mcp_section = f"\nFERRAMENTAS MCP EXTRAS DETECTADAS VIA SERVIDOR EXTERNO (Protocolo MCP):\n{tools_str}\n"

        prompt_content = self.history[0]["content"]
        if "[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]" in prompt_content:
            self.history[0]["content"] = prompt_content.replace("[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]", mcp_section)
        else:
            new_content = re.sub(r'\nFERRAMENTAS MCP EXTRAS DETECTADAS.*?(\n\n|$)', lambda m: '\n' + mcp_section + '\n\n', prompt_content, flags=re.DOTALL)
            self.history[0]["content"] = new_content

    async def start_background_services(self):
        if self.is_master:
            asyncio.create_task(self.scheduler.run())
            asyncio.create_task(self.heartbeat.run())
            await self.start_pty_bridge()
            console.print(f"[bold green]🚀 [{self.name}] Motores Proativos (Scheduler, Heartbeat & PTY Bridge) iniciados![/bold green]")

    async def start_pty_bridge(self):
        bridge_path = os.path.join(os.path.dirname(__file__), "terminal", "pty_bridge.js")
        if not os.path.exists(bridge_path):
            return

        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', 9001)) == 0:
                    console.print("[dim]>> [PTY Master] Ponte PTY já detectada na porta 9001. Reusando...[/dim]")
                    return

            console.print("[dim]>> [PTY Master] Inicializando Ponte PTY persistente (node-pty)...[/dim]")
            self.pty_bridge_process = await asyncio.create_subprocess_shell(
                f"node {bridge_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.sleep(2.0)
        except Exception as e:
            console.print(f"[warning]Falha ao iniciar PTY Bridge: {e}[/warning]")

    async def close_browser(self):
        await self.browser.close()
        if self.mcp_hub:
            try:
                await self.mcp_hub.cleanup()
            except Exception:
                pass

    async def init_browser(self):
        await self.browser.init()

    # Métodos delegados para retrocompatibilidade
    async def execute_terminal_command(self, command: str, timeout_seconds: int = 45) -> str:
        return await self.tool_executor.execute_terminal_command(command, timeout_seconds)

    async def run_browser_action(self, action: str, param: str) -> str:
        return await self.browser.run_action(action, param)

    async def run_workspace_action(self, action: str, param: str) -> str:
        return await self.tool_executor.run_workspace_action(action, param)

    async def execute_gmail_action(self, action: str, param: str) -> str:
        return await execute_gmail_action(action, param)

    async def execute_spotify_action(self, action: str, param: str) -> str:
        return await execute_spotify_action(action, param)

    async def execute_youtube_action(self, action: str, param: str) -> str:
        return await execute_youtube_action(action, param)

    async def execute_github_action(self, action: str, param: str) -> str:
        return await self.tool_executor.execute_github_action(action, param)

    async def execute_social_send(self, action: str, param: str) -> str:
        return await self.tool_executor.execute_social_send(action, param)

    async def execute_whatsapp_read(self, action: str, param: str) -> str:
        return await self.tool_executor.execute_whatsapp_read(action, param)

    async def get_embedding(self, text: str):
        try:
            if self.provider == "gemini":
                return None
            elif self.provider == "mistral":
                ret = self.mistral_client.embeddings(model="mistral-embed", inputs=[text[:2000]])
                if hasattr(ret, "data") and len(ret.data) > 0:
                    return ret.data[0].embedding
        except Exception:
            pass
        return None

    async def update_system_prompt_with_memory(self):
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

        import datetime
        current_content = self.history[0]["content"]

        new_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        current_content = re.sub(
            r'Data e hora atual do sistema: .*? \[DYNAMIC_DATE\]',
            f"Data e hora atual do sistema: {new_date} [DYNAMIC_DATE]",
            current_content
        )

        base_prompt = current_content.split("\n--- SOUL.md")[0].split("\n--- MEMÓRIA")[0]
        self.history[0] = {"role": "system", "content": base_prompt + soul_data + memory_data}

    async def check_compaction(self):
        char_count = sum(len(msg.get("content", "")) for msg in self.history[1:] if msg.get("content"))

        if char_count > 15000:
            console.print(f"[dim yellow][SISTEMA] Iniciando flush de memória silencioso (Compaction)... ({char_count:,} caracteres nas mensagens)[/dim yellow]")

            last_user_msg = self.history.pop()
            hist_len_before = len(self.history)

            compaction_prompt = "A sessão está no limite de contexto. Você DEVE armazenar TODO O CONHECIMENTO CRUCIAL recém-aprendido nesta sessão usando FILE_APPEND em MEMORY.md ou criando anotações com FILE_WRITE. Se não houver nada importante a guardar, responda única e puramente com o texto: NO_REPLY."

            self.history.append({"role": "user", "content": compaction_prompt})
            await self.ask(None, is_tool_response=True, silent=True)

            self.history = self.history[:hist_len_before]

            new_history = [self.history[0]]
            recent_msgs = self.history[1:][-4:]
            for msg in recent_msgs:
                if msg.get("content") and "[SISTEMA:" in msg["content"] and len(msg["content"]) > 1000:
                    msg["content"] = msg["content"][:1000] + "\n... [RESULTADO TRUNCADO PELO SISTEMA PARA POUPAR RAM]"
                new_history.append(msg)

            self.history = new_history
            self.history.append(last_user_msg)

            new_char_count = sum(len(msg.get("content", "")) for msg in self.history[1:] if msg.get("content"))
            console.print(f"[dim green][SISTEMA] Contexto compactado! {char_count:,} → {new_char_count:,} caracteres (mantidas últimas 4 mensagens)[/dim green]")

    async def transcribe_audio(self, audio_path: str) -> str:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            return ""

        console.print("[info]🎙️ Transcrevendo áudio recebido via Mistral Voxtral...[/info]")
        try:
            import aiohttp
            url = "https://api.mistral.ai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}

            with open(audio_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('model', 'voxtral-mini-latest')
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

    async def ask(
        self,
        prompt: str | None = None,
        is_tool_response: bool = False,
        silent: bool = False,
        stream_callback=None,
        tool_callback=None,
        reply_callback=None,
        requester: dict | None = None,
        _empty_retry: int = 0
    ):
        if _empty_retry >= 3:
            return "..."

        if reply_callback is not None:
            self._current_reply_callback = reply_callback

        if not self.mistral_client and not self.openai_client and not self.gemini_client:
            msg = "[SISTEMA: Nenhuma IA (Mistral, Gemini, OpenRouter ou OpenCode Zen) configurada. Verifique suas chaves de API no arquivo .env ou no painel.]"
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

                if requester.get("session_key"):
                    try:
                        from sessions import SessionStore, SessionKey
                        s_store = SessionStore()
                        s_key = SessionKey.parse(requester["session_key"])
                        s_hist = s_store.load_history(s_key)
                        if s_hist and len(self.history) <= 1:
                            self.history.extend(s_hist[-20:])
                    except Exception:
                        pass
            self.history.append({"role": "user", "content": final_prompt})

        if not is_tool_response and not silent:
            await self.update_system_prompt_with_memory()
            await self.update_mcp_tools_in_prompt()
            await self.check_compaction()

        if not is_tool_response and not silent:
            console.print(f"\n[moltyclaw]{self.name}:[/moltyclaw]", end=" ")

        self.is_busy = True
        try:
            response_chunks = await stream_llm(
                provider=self.provider,
                model=self.model,
                history=self.history,
                mistral_client=self.mistral_client,
                openai_client=self.openai_client,
                gemini_client=self.gemini_client,
                ollama_client=self.ollama_client,
                stream_callback=stream_callback,
                silent=silent,
                console=console
            )

            if not is_tool_response and not silent:
                print()
            elif is_tool_response and not silent:
                print()

            if not response_chunks.strip():
                return await self.ask(
                    None,
                    is_tool_response=True,
                    silent=silent,
                    stream_callback=stream_callback,
                    tool_callback=tool_callback,
                    reply_callback=None,
                    requester=None,
                    _empty_retry=(_empty_retry or 0) + 1
                )

            if "NO_REPLY" in response_chunks:
                self.history.append({"role": "assistant", "content": response_chunks})
                return "Resumo efetuado."

            cmd_data = parse_llm_tool_call(response_chunks)

            if response_chunks.strip():
                self.history.append({"role": "assistant", "content": response_chunks})
            else:
                self.history.append({"role": "assistant", "content": "..."})

            if cmd_data:
                try:
                    action = cmd_data.get("action")
                    param = cmd_data.get("param", "")

                    if action is None:
                        raise ValueError(f"Campo 'action' ausente no cmd_data: {cmd_data}")

                    return await self.tool_executor.execute_tool(
                        action=action,
                        param=param,
                        cmd_data=cmd_data,
                        silent=silent,
                        stream_callback=stream_callback,
                        tool_callback=tool_callback
                    )
                except Exception as e:
                    err_msg = f"Erro na execução da Tool: {str(e)} para o comando: {cmd_data}"
                    console.print(f"\n[error]{err_msg}[/error]")
                    self.history.append({"role": "user", "content": f"[SISTEMA: ERRO] {err_msg}. Corrija a chamada da ferramenta!"})
                    return await self.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

            stripped_response = re.sub(r'<think>.*?</think>', '', response_chunks, flags=re.DOTALL).strip()
            if not stripped_response and "<think>" in response_chunks:
                stripped_response = re.sub(r'</?think>', '', response_chunks, flags=re.IGNORECASE).strip()

            if requester and requester.get("session_key") and not is_tool_response:
                try:
                    from sessions import SessionStore, SessionKey
                    s_store = SessionStore()
                    s_key = SessionKey.parse(requester["session_key"])
                    s_store.save_history(s_key, self.history[1:], peer_name=requester.get("name"))
                except Exception:
                    pass

            return stripped_response

        except Exception as e:
            err_msg = f"Erro ao comunicar com {self.provider.capitalize()}: {e}"
            console.print(f"[error]{err_msg}[/error]")
            return err_msg
        finally:
            self.is_busy = False

    def _get_available_agents(self):
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
                    except Exception:
                        pass
        return agent_configs

    def _load_agent_config(self):
        if self.is_master:
            return {}

        config_path = os.path.join(self.workspace_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _load_soul(self):
        content = self._read_workspace_file("SOUL.md")
        if content:
            return f"\n📜 SUA ALMA (SOUL.md):\n{content}\n"
        return ""

    def _load_identity(self):
        return self._read_workspace_file("IDENTITY.md")

    def _load_user(self):
        return self._read_workspace_file("USER.md")

    def _load_bootstrap(self):
        return self._read_workspace_file("BOOTSTRAP.md")

    def _load_memory(self):
        content = self._read_workspace_file("MEMORY.md")
        return content if content else "Nenhuma memória registrada ainda."

    def _read_workspace_file(self, filename: str) -> str:
        path = os.path.join(self.workspace_dir, filename)

        if not os.path.exists(path):
            old_path = os.path.join(self.base_dir, filename)
            if os.path.exists(old_path):
                try:
                    shutil.move(old_path, path)
                except Exception:
                    path = old_path
            else:
                if self.is_master and os.path.exists(filename):
                    path = filename

        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""

    def _build_tools_list(self):
        all_tools = {
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

            "CMD": '"CMD" (param: comando de terminal)',
            "FS_LIST": '"FS_LIST" (param: "caminho_absoluto_opcional") - Lista diretórios e arquivos de um caminho do sistema de arquivos NATIVO, sem precisar do terminal. Mais rápido e mais confiável que CMD para navegação de pastas. Se param vazio, lista o diretório home do usuário.',
            "CANVAS_UPDATE": '"CANVAS_UPDATE" (param: "id_do_artefato | typo (html, markdown, svg, react) | CODE/CONTENT") - Renderiza em tempo real o código/documento num painel visual interativo na Web UI.',

            "READ_EMAILS": '"READ_EMAILS" (param: limite)',
            "SEND_EMAIL": '"SEND_EMAIL" (param: destinatario | assunto | corpo)',
            "DELETE_EMAIL": '"DELETE_EMAIL" (param: id_do_email)',

            "SPOTIFY_PLAY": '"SPOTIFY_PLAY" (param: música/URI)',
            "SPOTIFY_PAUSE": '"SPOTIFY_PAUSE" (param: "")',
            "SPOTIFY_SEARCH": '"SPOTIFY_SEARCH" (param: termo)',
            "SPOTIFY_ADD_QUEUE": '"SPOTIFY_ADD_QUEUE" (param: URI)',
            "YOUTUBE_SUMMARIZE": '"YOUTUBE_SUMMARIZE" (param: link)',
            "VOICE_REPLY": '"VOICE_REPLY" (param: "texto de reposta em voz. Opcional: Adicione | ID_DO_USUARIO apenas se quiser mandar ativamente para OUTRA PESSOA. NÃO adicione ID ou plataforma se for apenas responder a conversa atual!")',

            "GITHUB_LIST_REPOS": '"GITHUB_LIST_REPOS" (param: "usuario_opcional") - Lista repositórios públicos/privados acessíveis pelo token.',
            "GITHUB_LIST_ISSUES": '"GITHUB_LIST_ISSUES" (param: "owner/repo | state:open|closed|all | limit:10") - Lista issues de um repositório.',
            "GITHUB_CREATE_ISSUE": '"GITHUB_CREATE_ISSUE" (param: "owner/repo | titulo | corpo_opcional") - Cria uma nova issue num repositório.',
            "GITHUB_LIST_PRS": '"GITHUB_LIST_PRS" (param: "owner/repo | state:open|closed|all") - Lista Pull Requests de um repositório.',
            "GITHUB_GET_PR": '"GITHUB_GET_PR" (param: "owner/repo | numero_pr") - Obtém detalhes, arquivos alterados e status de um Pull Request.',
            "GITHUB_CREATE_COMMENT": '"GITHUB_CREATE_COMMENT" (param: "owner/repo | numero_issue_ou_pr | comentario") - Adiciona comentário em uma Issue ou PR.',
            "GITHUB_GET_FILE": '"GITHUB_GET_FILE" (param: "owner/repo | caminho_arquivo | branch_opcional") - Lê o conteúdo de um arquivo no repositório.',
            "GITHUB_LIST_COMMITS": '"GITHUB_LIST_COMMITS" (param: "owner/repo | branch_ou_sha_opcional | limit:10") - Lista commits recentes de um repositório.',

            "WHATSAPP_SEND": '"WHATSAPP_SEND" (param: "numero | opcional texto | opcional caminho arquivo absoluto")',
            "WHATSAPP_GET_CONTACTS": '"WHATSAPP_GET_CONTACTS" (param: "") - Lista todos os contatos salvos na agenda do WhatsApp com nome, número e ID.',
            "WHATSAPP_GET_CHATS": '"WHATSAPP_GET_CHATS" (param: "") - Lista as conversas recentes do WhatsApp com nome, ID, mensagens não lidas e prévia da última mensagem.',
            "WHATSAPP_GET_MESSAGES": '"WHATSAPP_GET_MESSAGES" (param: "chat_id | limite_opcional") - Lê as últimas N mensagens de uma conversa específica. Use o ID retornado por WHATSAPP_GET_CHATS ou WHATSAPP_GET_CONTACTS. Limite padrão: 20.',
            "DISCORD_SEND": '"DISCORD_SEND" (param: "id_usuario_ou_chat | opcional texto | opcional caminho arquivo absoluto")',
            "TELEGRAM_SEND": '"TELEGRAM_SEND" (param: "id_ou_username | opcional texto | opcional caminho arquivo absoluto")',
            "X_POST": '"X_POST" (param: "texto do tweet de ate 280 chars")',
            "BLUESKY_POST": '"BLUESKY_POST" (param: "texto do skeet de ate 300 chars para postar no Bluesky")',

            "FILE_WRITE": '"FILE_WRITE" (param: "caminho_relativo | conteudo completo") - Cria ou sobrescreve um arquivo no workspace (ex: "SOUL.md | nova alma", "roteiro.txt | cena 1...")',
            "FILE_APPEND": '"FILE_APPEND" (param: "caminho_relativo | conteudo") - Adiciona conteúdo ao final do arquivo (ex: "MEMORY.md | - Gosta de azul")',
            "FILE_READ": '"FILE_READ" (param: "caminho_relativo") - Lê todo o conteúdo de um arquivo',
            "MEMORY_SEARCH": '"MEMORY_SEARCH" (param: busca) - Busca semanticamente na memória de longo prazo e diários',
            "SKILL_USE": '"SKILL_USE" (param: "nome_da_skill") - Ativa uma skill modular e carrega suas instruções detalhadas para o contexto atual.',

            "SCHEDULE_TASK": '"SCHEDULE_TASK" (param: "Nome do Job | Intervalo (em minutos) | Payload do Prompt") - Agenda uma tarefa recorrente que o agente executa sozinho.',
            "LIST_TASKS": '"LIST_TASKS" (param: "") - Lista todas as tarefas agendadas e seus estados.',
            "DELETE_TASK": '"DELETE_TASK" (param: "ID_da_Tarefa") - Remove uma tarefa agendada.',
        }

        if not self.browser_enabled:
            browser_keys = ["OPEN_BROWSER", "GOTO", "CLICK", "TYPE", "PRESS_ENTER", "PRESS_KEY", "READ_PAGE", "INSPECT_PAGE", "SCREENSHOT", "SCROLL_DOWN", "DDG_SEARCH"]
            for k in browser_keys:
                if k in all_tools:
                    del all_tools[k]

        active_features = []

        if self.is_master:
            active_features.append("Ações suportadas no JSON:")
            for tool_desc in all_tools.values():
                active_features.append(tool_desc)

            available_agents = self._get_available_agents()
            if available_agents:
                other_agents = [a for a in available_agents if a['id'] != self.agent_id]
                if other_agents:
                    agent_list_str = "\n".join([f"- {a['id']}: {a['name']} ({a['description']})" for a in other_agents])
                    active_features.append(f'\n🤖 AGENTES ESPECIALISTAS DISPONÍVEIS:\n{agent_list_str}')
        else:
            active_features.append("Ações suportadas no JSON (você tem acesso limitado às seguintes ferramentas):")
            for tool_name in (self.allowed_tools_local or []):
                if tool_name in all_tools:
                    active_features.append(all_tools[tool_name])

            if self.allowed_tools_local and ("SESSION_SPAWN" in self.allowed_tools_local or "CALL_AGENT" in self.allowed_tools_local):
                available_agents = self._get_available_agents()
                if available_agents:
                    other_agents = [a for a in available_agents if a['id'] != self.agent_id]
                    if other_agents:
                        agent_list_str = "\n".join([f"- {a['id']}: {a['name']} ({a['description']})" for a in other_agents])
                        active_features.append(f'\n🤖 AGENTES ESPECIALISTAS DISPONÍVEIS:\n{agent_list_str}')

        return "\n".join(active_features)

    def _is_tool_allowed(self, action: str) -> bool:
        if self.is_master:
            return True
        if not self.allowed_tools_local:
            return True
        return action in self.allowed_tools_local


async def interactive_shell():
    class MoltyPrompt(Prompt):
        prompt_suffix = ""

    agent = MoltyClaw()
    await agent.init_browser()
    if agent.mcp_hub:
        await agent.mcp_hub.connect_servers()

    console.clear()

    logo = [
        "███╗   ███╗ ██████╗ ██╗  ████████╗██╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗",
        "████╗ ████║██╔═══██╗██║  ╚══██╔══╝╚██╗ ██╔╝██╔════╝██║     ██╔══██╗██║    ██║",
        "██╔████╔██║██║   ██║██║     ██║    ╚████╔╝ ██║     ██║     ███████║██║ █╗ ██║",
        "██║╚██╔╝██║██║   ██║██║     ██║     ╚██╔╝  ██║     ██║     ██╔══██║██║███╗██║",
        "██║ ╚═╝ ██║╚██████╔╝███████╗██║      ██║   ╚██████╗███████╗██║  ██║╚███╔███╔╝",
        "╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝      ╚═╝    ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝ "
    ]

    console.print()
    for line in logo:
        formatted_line = ""
        n = len(line)
        for i, char in enumerate(line):
            if char == " ":
                formatted_line += " "
            else:
                g = int(60 + (i / n) * 170)
                color = f"#ff{g:02x}00"
                formatted_line += f"[{color}]{char}[/]"
        console.print(formatted_line)

    status_browser = "[bold green]Ativado[/bold green]" if agent.browser_enabled else "[bold red]Desativado[/bold red]"
    console.print(Panel.fit(
        f"[bold cyan]🤖 MoltyClaw - Terminal Inteligente[/bold cyan]\n"
        f"[dim]Provedor:[/dim] [bold #ff9c59]{agent.provider.upper()}[/bold #ff9c59]  |  [dim]Modelo:[/dim] [bold white]{agent.model}[/bold white]\n"
        f"[dim]Modo Navegador:[/dim] {status_browser}",
        border_style="cyan"
    ))
    console.print()

    _turn_count = 0

    while True:
        try:
            console.print("─" * console.width, style="dim")
            sys.stdout.write(" ❯ \n")
            console.print("─" * console.width, style="dim")

            sys.stdout.write("\033[2A\033[3C")
            sys.stdout.flush()

            user_input = sys.stdin.readline().strip()

            if not user_input:
                sys.stdout.write("\n")
                sys.stdout.flush()
                continue

            sys.stdout.write("\033[2K")
            sys.stdout.write("\033[A\033[2K")
            sys.stdout.write("\033[A\033[2K")
            sys.stdout.flush()

            if _turn_count > 0:
                divider = "─" * console.width
                n = len(divider)
                formatted_divider = ""
                for i, char in enumerate(divider):
                    g = int(60 + (i / n) * 170)
                    color = f"#ff{g:02x}00"
                    formatted_divider += f"[{color}]{char}[/]"
                console.print(formatted_divider)

            console.print(f"[bold blue]Você:[/bold blue] {user_input}")

            if user_input.lower() in ['sair', 'exit', 'quit']:
                console.print("[moltyclaw]MoltyClaw:[/moltyclaw] Fechando o navegador e desligando! 👋")
                await agent.close_browser()
                break

            if user_input.startswith("!cmd "):
                cmd = user_input[5:]
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                    progress.add_task(description=f"Executando '{cmd}'...", total=None)
                    result = await agent.execute_terminal_command(cmd)
                console.print(Panel(result, title="[green]Terminal Output[/green]", border_style="green"))
                continue

            _t0 = time.perf_counter()
            await agent.ask(user_input)
            _elapsed = time.perf_counter() - _t0
            console.print(f"[dim]⏱ {_elapsed:.1f}s[/dim]")
            _turn_count += 1

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
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore[deprecated]
    asyncio.run(interactive_shell())
