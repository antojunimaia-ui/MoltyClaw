"""
MoltyClaw — Queued Turn Manager (Per-Session Concurrency)
Inspirado no chat-queued-turns.ts do OpenClaw.

Garante que:
1. Mensagens da MESMA sessão (SessionKey) sejam processadas em fila sequencial (evita race conditions no histórico).
2. Mensagens de SESSÕES DIFERENTES sejam processadas concorrentemente em paralelo sem travamentos.
"""

import asyncio
from typing import Dict, Any, Callable, Awaitable, TypeVar
from rich.console import Console

console = Console()
T = TypeVar("T")

class QueuedTurnManager:
    """Gerencia travas e filas assíncronas por SessionKey."""

    def __init__(self):
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_session_lock(self, session_key_str: str) -> asyncio.Lock:
        async with self._global_lock:
            if session_key_str not in self._locks:
                self._locks[session_key_str] = asyncio.Lock()
            return self._locks[session_key_str]

    async def run_turn(self, session_key_str: str, func: Callable[[], Awaitable[T]]) -> T:
        """Executa um turno de conversa garantindo isolamento de trava por SessionKey."""
        lock = await self._get_session_lock(session_key_str)
        async with lock:
            return await func()
