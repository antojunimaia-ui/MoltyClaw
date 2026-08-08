"""
MoltyClaw — Unified Session Key & Session Store System
Inspirado no sistema de sessões do OpenClaw.

Chave de Sessão no formato: <agent_id>:<channel>:<peer_id>
Exemplo: MoltyClaw:telegram:12984712
"""

import os
import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from rich.console import Console

console = Console()
MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")
SESSIONS_DIR = os.path.join(MOLTY_DIR, "sessions")

@dataclass
class SessionKey:
    agent_id: str = "MoltyClaw"
    channel: str = "cli"
    peer_id: str = "default"

    @property
    def key_str(self) -> str:
        # Normaliza strings
        a_id = (self.agent_id or "MoltyClaw").strip().lower()
        chan = (self.channel or "cli").strip().lower()
        peer = (self.peer_id or "default").strip().lower()
        return f"{a_id}:{chan}:{peer}"

    @classmethod
    def parse(cls, raw: str) -> "SessionKey":
        parts = raw.split(":")
        if len(parts) >= 3:
            return cls(agent_id=parts[0], channel=parts[1], peer_id=":".join(parts[2:]))
        elif len(parts) == 2:
            return cls(agent_id="MoltyClaw", channel=parts[0], peer_id=parts[1])
        return cls(agent_id="MoltyClaw", channel="cli", peer_id=raw or "default")


@dataclass
class SessionMetadata:
    session_key: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    peer_name: Optional[str] = None
    channel: str = "cli"
    agent_id: str = "MoltyClaw"
    message_count: int = 0


class SessionStore:
    """Gerencia a persistência e isolamento do histórico e metadados por SessionKey."""

    def __init__(self, sessions_dir: str = SESSIONS_DIR):
        self.sessions_dir = sessions_dir
        os.makedirs(self.sessions_dir, exist_ok=True)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}

    def _get_file_path(self, session_key: SessionKey) -> str:
        # Substitui caracteres inválidos em nomes de arquivos de SO
        safe_filename = session_key.key_str.replace(":", "_").replace("/", "_").replace("\\", "_")
        return os.path.join(self.sessions_dir, f"{safe_filename}.json")

    def load_history(self, session_key: SessionKey) -> List[Dict[str, Any]]:
        """Carrega o histórico de mensagens para uma chave de sessão específica."""
        k = session_key.key_str
        if k in self._cache:
            return self._cache[k]

        file_path = self._get_file_path(session_key)
        if not os.path.exists(file_path):
            self._cache[k] = []
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                history = data.get("history", [])
                self._cache[k] = history
                return history
        except Exception as e:
            console.print(f"[dim red]Erro ao carregar histórico da sessão {k}: {e}[/dim red]")
            self._cache[k] = []
            return []

    def save_history(
        self,
        session_key: SessionKey,
        history: List[Dict[str, Any]],
        peer_name: Optional[str] = None
    ):
        """Salva o histórico de mensagens de uma sessão isolada em disco."""
        k = session_key.key_str
        self._cache[k] = history

        file_path = self._get_file_path(session_key)
        metadata = SessionMetadata(
            session_key=k,
            updated_at=time.time(),
            peer_name=peer_name,
            channel=session_key.channel,
            agent_id=session_key.agent_id,
            message_count=len(history)
        )

        payload = {
            "metadata": asdict(metadata),
            "history": history
        }

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            console.print(f"[dim red]Erro ao salvar sessão {k}: {e}[/dim red]")

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Lista todas as sessões ativas com metadados."""
        sessions = []
        if not os.path.exists(self.sessions_dir):
            return sessions

        for filename in os.listdir(self.sessions_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.sessions_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        meta = data.get("metadata", {})
                        sessions.append(meta)
                except Exception:
                    pass
        return sessions
