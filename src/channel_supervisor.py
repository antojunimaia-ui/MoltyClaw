"""
MoltyClaw — Channel Supervisor (Hot-Reload & Resilient Connectors)
Inspirado no server-channels.ts do OpenClaw.

Gerencia o ciclo de vida (start, stop, restart, status) de cada conector de canal
(WhatsApp, Telegram, Discord, Twitter, Bluesky) de forma isolada.
"""

import asyncio
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from rich.console import Console

console = Console()

class ChannelSnapshot:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.status = "stopped"  # "stopped" | "starting" | "running" | "error"
        self.last_start_at: Optional[float] = None
        self.last_error: Optional[str] = None
        self.reconnect_attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "status": self.status,
            "last_start_at": self.last_start_at,
            "last_error": self.last_error,
            "reconnect_attempts": self.reconnect_attempts,
        }


class ChannelSupervisor:
    """Supervisor de conectores de canais com autorestart e isolamento de falhas."""

    def __init__(self, hub_instance=None):
        self.hub = hub_instance
        self.snapshots: Dict[str, ChannelSnapshot] = {
            "whatsapp": ChannelSnapshot("whatsapp"),
            "telegram": ChannelSnapshot("telegram"),
            "discord": ChannelSnapshot("discord"),
            "twitter": ChannelSnapshot("twitter"),
            "bluesky": ChannelSnapshot("bluesky"),
        }
        self._tasks: Dict[str, asyncio.Task] = {}

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Retorna o snapshot de status de todos os canais."""
        return {cid: snap.to_dict() for cid, snap in self.snapshots.items()}

    async def start_channel(self, channel_id: str, runner_func: Callable[[], Awaitable[None]]):
        """Inicia um conector de canal sob supervisão assíncrona."""
        cid = channel_id.lower()
        if cid not in self.snapshots:
            self.snapshots[cid] = ChannelSnapshot(cid)

        snap = self.snapshots[cid]
        snap.status = "starting"
        snap.last_start_at = time.time()
        console.print(f"[dim cyan]📡 [ChannelSupervisor] Iniciando conector '{cid}'...[/dim cyan]")

        async def _supervised_wrapper():
            backoff = 2.0
            max_backoff = 60.0
            while True:
                try:
                    snap.status = "running"
                    snap.last_error = None
                    await runner_func()
                    snap.status = "stopped"
                    break
                except asyncio.CancelledError:
                    snap.status = "stopped"
                    console.print(f"[dim yellow]📡 [ChannelSupervisor] Conector '{cid}' parado pelo operador.[/dim yellow]")
                    break
                except Exception as e:
                    snap.status = "error"
                    snap.last_error = str(e)
                    snap.reconnect_attempts += 1
                    console.print(f"[bold red]⚠️ [ChannelSupervisor] Erro no conector '{cid}': {e}. Reconectando em {backoff:.1f}s...[/bold red]")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2.0, max_backoff)

        # Cancela tarefa existente se houver
        await self.stop_channel(cid)
        self._tasks[cid] = asyncio.create_task(_supervised_wrapper())

    async def stop_channel(self, channel_id: str):
        """Para a execução de um conector específico sem afetar o resto da aplicação."""
        cid = channel_id.lower()
        if cid in self._tasks:
            task = self._tasks[cid]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self._tasks[cid]

        if cid in self.snapshots:
            self.snapshots[cid].status = "stopped"
