"""
AgentHub — Instância Única Compartilhada do MoltyClaw

Garante que existe apenas UM agente MoltyClaw rodando, independente de quantos
canais (WebUI, Discord, Telegram, WhatsApp...) estejam ativos simultaneamente.

Uso:
    from agent_hub import get_hub

    hub = get_hub()
    reply = hub.ask_sync("Olá!", channel="telegram", peer_id="123456")

    # Ou async (dentro de um coroutine):
    reply = await hub.ask("Olá!", channel="telegram", peer_id="123456")
"""

import asyncio
import os
import sys
import threading
import logging
import subprocess
from typing import Optional, Callable, Awaitable, Dict, Any

# Garante que src/ está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
console = Console()

# ── Singleton ─────────────────────────────────────────────────────────────────

_hub_instance: Optional["AgentHub"] = None
_hub_lock = threading.Lock()


def get_hub() -> "AgentHub":
    """Retorna (ou cria) a instância única do AgentHub."""
    global _hub_instance
    if _hub_instance is None:
        with _hub_lock:
            if _hub_instance is None:
                _hub_instance = AgentHub()
                _hub_instance.start()
    return _hub_instance


# ── AgentHub ──────────────────────────────────────────────────────────────────

class AgentHub:
    """
    Mantém uma única instância do MoltyClaw rodando em uma thread dedicada
    com seu próprio event loop asyncio.

    Todos os canais (WebUI, Discord, Telegram, WhatsApp...) chamam ask() ou
    ask_sync() para enviar mensagens ao agente compartilhado.
    """

    def __init__(self):
        self.agent = None          # MoltyClaw instance
        self.scheduler = None      # SchedulerManager instance
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.ready = False
        self._thread: Optional[threading.Thread] = None

    # ── Inicialização ─────────────────────────────────────────────────────────

    def start(self):
        """Inicia a thread dedicada com o event loop e o agente."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AgentHubThread")
        self._thread.start()

        # Aguarda o agente ficar pronto (máx 60s)
        import time
        deadline = time.time() + 60
        while not self.ready and time.time() < deadline:
            time.sleep(0.1)

        if not self.ready:
            console.print("[bold red]⚠️  AgentHub: timeout aguardando inicialização do agente![/bold red]")

    def _run_loop(self):
        """Corpo da thread dedicada."""
        if os.name == "nt":
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._init_agent())
        self.loop.run_forever()

    async def _init_agent(self):
        """Inicializa o MoltyClaw Master e seus serviços de background."""
        from moltyclaw import MoltyClaw
        from scheduler import SchedulerManager

        console.print("[dim cyan]>> AgentHub: Inicializando instância única do MoltyClaw...[/dim cyan]")

        from sessions import SessionStore, SessionKey
        from queued_turns import QueuedTurnManager
        from channel_supervisor import ChannelSupervisor

        self.session_store = SessionStore()
        self.turn_manager = QueuedTurnManager()
        self.channel_supervisor = ChannelSupervisor(self)
        self.agent = MoltyClaw(name="MoltyClaw")

        # Browser
        await self.agent.init_browser()

        # MCP
        if self.agent.mcp_hub:
            await self.agent.mcp_hub.connect_servers()

        # Scheduler + Heartbeat
        self.scheduler = SchedulerManager(self.agent)
        self.loop.create_task(self.scheduler.run())

        await self.agent.start_background_services()

        self.ready = True
        console.print("[bold green]✅ AgentHub: Instância única pronta com SessionStore & Control Plane![/bold green]")

    # ── API pública ───────────────────────────────────────────────────────────

    async def ask(
        self,
        message: str,
        *,
        channel: Optional[str] = None,
        peer_id: Optional[str] = None,
        peer_name: Optional[str] = None,
        silent: bool = False,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
        tool_callback: Optional[Callable[[str], Awaitable[None]]] = None,
        reply_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> str:
        """
        Envia uma mensagem ao agente compartilhado com isolamento por SessionKey e Fila de Turnos.
        """
        if not self.ready or self.agent is None:
            return "⚠️ Agente ainda não está pronto. Aguarde alguns segundos."

        from sessions import SessionKey
        s_key = SessionKey(
            agent_id=self.agent.agent_id or "MoltyClaw",
            channel=channel or "cli",
            peer_id=peer_id or "default"
        )

        # Injeta contexto do canal no prompt para o agente saber de onde veio
        enriched = message
        if channel and channel not in ("webui", "cli"):
            origin_info = f"\n\n[SISTEMA: Esta mensagem chegou pelo canal '{channel.upper()}'"
            if peer_name:
                origin_info += f" do usuário '{peer_name}'"
            if peer_id:
                origin_info += f" (ID: {peer_id})"
            origin_info += ".]"
            enriched = message + origin_info

        requester = None
        if peer_id or peer_name:
            requester = {
                "id": peer_id or "",
                "name": peer_name or peer_id or "Desconhecido",
                "platform": channel or "unknown",
                "session_key": s_key.key_str,
            }

        async def _do_turn():
            return await self.agent.ask(
                enriched,
                silent=silent,
                stream_callback=stream_callback,
                tool_callback=tool_callback,
                reply_callback=reply_callback,
                requester=requester,
            )

        # Executa o turno isolado na fila de turnos da SessionKey
        return await self.turn_manager.run_turn(s_key.key_str, _do_turn)

    def ask_sync(
        self,
        message: str,
        *,
        channel: Optional[str] = None,
        peer_id: Optional[str] = None,
        peer_name: Optional[str] = None,
        timeout: float = 300.0,
    ) -> str:
        """
        Versão síncrona de ask(). Usa run_coroutine_threadsafe para chamar
        de qualquer thread externa (bots, WebUI Flask, etc.).

        Args:
            timeout: Segundos máximos de espera (padrão: 5 minutos).
        """
        if not self.ready or self.loop is None:
            return "⚠️ Agente ainda não está pronto."

        future = asyncio.run_coroutine_threadsafe(
            self.ask(message, channel=channel, peer_id=peer_id, peer_name=peer_name),
            self.loop,
        )
        return future.result(timeout=timeout)

    def ask_sync_streaming(
        self,
        message: str,
        stream_q,
        *,
        channel: Optional[str] = None,
        peer_id: Optional[str] = None,
        peer_name: Optional[str] = None,
    ):
        """
        Versão síncrona com streaming via queue thread-safe.
        Coloca ("token", texto), ("tool", texto) e ("done", None) na queue.
        Usada pela WebUI Flask para SSE.
        """
        if not self.ready or self.loop is None:
            stream_q.put(("error", "Agente não está pronto."))
            return

        import re

        async def stream_cb(token: str):
            stream_q.put(("token", token))

        async def tool_cb(msg: str):
            stream_q.put(("tool", msg))

        async def run():
            try:
                res = await self.ask(
                    message,
                    channel=channel,
                    peer_id=peer_id,
                    peer_name=peer_name,
                    stream_callback=stream_cb,
                    tool_callback=tool_cb,
                )
                # Repassa marcadores especiais (AUDIO_REPLY, etc.)
                if res and isinstance(res, str) and "[AUDIO_REPLY:" in res:
                    match = re.search(r'\[AUDIO_REPLY:\s*([^\]]+)\]', res)
                    if match:
                        filename = os.path.basename(match.group(1).strip())
                        stream_q.put(("token", f"\n\n[AUDIO_REPLY: {filename}]\n\n"))
                stream_q.put(("done", None))
            except Exception as e:
                stream_q.put(("error", str(e)))

        asyncio.run_coroutine_threadsafe(run(), self.loop)

    def schedule_coroutine(self, coro):
        """Agenda uma coroutine no loop do AgentHub. Retorna um Future."""
        if self.loop is None:
            raise RuntimeError("AgentHub loop não iniciado.")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def transcribe_audio_sync(self, filepath: str, timeout: float = 60.0) -> str:
        """Transcreve áudio usando o agente compartilhado (síncrono)."""
        if not self.ready or self.loop is None:
            return ""
        future = asyncio.run_coroutine_threadsafe(
            self.agent.transcribe_audio(filepath),
            self.loop,
        )
        try:
            return future.result(timeout=timeout) or ""
        except Exception:
            return ""

    # ── Gerenciamento de Integrações ──────────────────────────────────────────

    def start_integration(self, name: str) -> bool:
        """
        Inicia uma integração (discord, telegram, whatsapp, twitter, bluesky)
        dentro do loop do AgentHub como uma task assíncrona, garantindo que
        todos os canais compartilhem a mesma instância do agente.

        Retorna True se iniciou com sucesso, False se já estava ativa ou falhou.
        """
        if not hasattr(self, "_integration_tasks"):
            self._integration_tasks: Dict[str, asyncio.Task] = {}
        if not hasattr(self, "_integration_processes"):
            self._integration_processes: Dict[str, list] = {}

        if name in self._integration_tasks and not self._integration_tasks[name].done():
            console.print(f"[dim yellow]Integração '{name}' já está ativa.[/dim yellow]")
            return False

        if self.loop is None:
            return False

        async def _run_discord():
            from integrations.discord_bot import MoltyClawDiscordBot
            from config_loader import get_config
            from initializer import MOLTY_DIR
            from dotenv import load_dotenv
            import discord

            load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)
            molty_config = get_config()
            d_cfg = molty_config.get("channels", {}).get("discord", {})
            token = d_cfg.get("bot_token") or os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
            if not token:
                console.print("[bold red]❌ Discord: DISCORD_TOKEN não encontrado.[/bold red]")
                return

            intents = discord.Intents.default()
            intents.message_content = True
            intents.voice_states = True
            client = MoltyClawDiscordBot(intents=intents, name="MoltyClaw (Discord)")
            await client.start(token)

        async def _run_telegram():
            from telegram.ext import ApplicationBuilder, MessageHandler, filters
            from integrations.telegram_bot import handle_message, post_init
            from config_loader import get_config
            from initializer import MOLTY_DIR
            from dotenv import load_dotenv

            load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)
            molty_config = get_config()
            t_cfg = molty_config.get("channels", {}).get("telegram", {})
            token = t_cfg.get("bot_token") or os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
            if not token:
                console.print("[bold red]❌ Telegram: TELEGRAM_TOKEN não encontrado.[/bold red]")
                return

            tg_app = ApplicationBuilder().token(token).post_init(post_init).build()
            tg_app.add_handler(MessageHandler(~filters.COMMAND, handle_message))
            await tg_app.initialize()
            await tg_app.start()
            await tg_app.updater.start_polling()
            # Mantém rodando até a task ser cancelada
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            finally:
                await tg_app.updater.stop()
                await tg_app.stop()
                await tg_app.shutdown()

        async def _run_whatsapp_server():
            from aiohttp import web as aio_web
            from integrations.whatsapp_server import handle_whatsapp_message

            aio_app = aio_web.Application()
            aio_app.router.add_post('/whatsapp', handle_whatsapp_message)
            runner = aio_web.AppRunner(aio_app)
            await runner.setup()
            site = aio_web.TCPSite(runner, '0.0.0.0', 8080)
            await site.start()
            console.print("[bold green]✅ WhatsApp server ouvindo em http://localhost:8080/whatsapp[/bold green]")
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                pass
            finally:
                await runner.cleanup()

        runner_map = {
            "discord": _run_discord,
            "telegram": _run_telegram,
            "whatsapp": _run_whatsapp_server,
        }

        if name in runner_map:
            # Roda dentro do loop do AgentHub — compartilha o mesmo processo
            task = asyncio.run_coroutine_threadsafe(
                self._wrap_integration(name, runner_map[name]()),
                self.loop,
            )
            self._integration_tasks[name] = task
            console.print(f"[bold green]✅ Integração '{name}' iniciada no AgentHub (processo único).[/bold green]")
            return True
        else:
            # Integrações sem runner nativo (twitter, bluesky) ainda usam subprocesso
            return self._start_subprocess_integration(name)

    async def _wrap_integration(self, name: str, coro):
        """Wrapper que captura erros de integrações e loga."""
        try:
            await coro
        except asyncio.CancelledError:
            console.print(f"[dim yellow]Integração '{name}' cancelada.[/dim yellow]")
        except Exception as e:
            console.print(f"[bold red]❌ Erro na integração '{name}': {e}[/bold red]")

    def _start_subprocess_integration(self, name: str) -> bool:
        """Fallback: inicia integrações sem runner nativo como subprocesso."""
        if not hasattr(self, "_integration_processes"):
            self._integration_processes: Dict[str, list] = {}

        BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        cmd_map = {
            "twitter": [f'"{sys.executable}" "{os.path.join(BASE_DIR, "src", "integrations", "twitter_bot.py")}"'],
            "bluesky": [f'"{sys.executable}" "{os.path.join(BASE_DIR, "src", "integrations", "bluesky_bot.py")}"'],
        }
        if name not in cmd_map:
            return False

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        procs = []
        for cmd in cmd_map[name]:
            p = subprocess.Popen(cmd, shell=True, env=env)
            procs.append(p)
        self._integration_processes[name] = procs
        return True

    def stop_integration(self, name: str) -> bool:
        """Para uma integração ativa."""
        if not hasattr(self, "_integration_tasks"):
            self._integration_tasks: Dict[str, asyncio.Task] = {}
        if not hasattr(self, "_integration_processes"):
            self._integration_processes: Dict[str, list] = {}

        stopped = False

        # Para tasks assíncronas
        if name in self._integration_tasks:
            task = self._integration_tasks.pop(name)
            if not task.done():
                self.loop.call_soon_threadsafe(task.cancel)
            stopped = True

        # Para subprocessos
        if name in self._integration_processes:
            for p in self._integration_processes.pop(name):
                try:
                    p.terminate()
                except Exception:
                    pass
            stopped = True

        return stopped

    def get_active_integrations(self) -> list:
        """Retorna lista de integrações ativas."""
        active = []
        if hasattr(self, "_integration_tasks"):
            for name, task in self._integration_tasks.items():
                if not task.done():
                    active.append(name)
        if hasattr(self, "_integration_processes"):
            for name, procs in self._integration_processes.items():
                if any(p.poll() is None for p in procs):
                    active.append(name)
        return active
