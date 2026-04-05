"""
SubAgent Registry — Inspirado no OpenClaw subagent-registry.ts
Rastreia sub-agentes rodando em background com asyncio.create_task()
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SubagentRun:
    run_id: str
    agent_id: str
    task: str
    requester_id: str          # agent_id de quem disparou a tarefa
    label: Optional[str] = None
    status: str = "pending"    # pending | running | done | error
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    agent_instance: Optional[object] = None # Guarda a instância viva (MoltyClaw) para permitir inspeção e envio de mensagens


# ── Storage em memória (persiste durante o processo) ──────────────────────────
_runs: dict[str, SubagentRun] = {}


def new_run_id() -> str:
    return str(uuid.uuid4())[:8]


def register(run: SubagentRun) -> None:
    _runs[run.run_id] = run


def get(run_id: str) -> Optional[SubagentRun]:
    return _runs.get(run_id)


def list_active() -> list[SubagentRun]:
    return [r for r in _runs.values() if r.status in ("pending", "running")]


def list_for_requester(requester_id: str) -> list[SubagentRun]:
    return [r for r in _runs.values() if r.requester_id == requester_id]


def summary() -> str:
    """Resumo humano dos runs ativos para o Master mostrar ao usuário."""
    active = list_active()
    if not active:
        return "Nenhum sub-agente rodando no momento."
    lines = []
    for r in active:
        elapsed = round(time.time() - (r.started_at or r.created_at), 0)
        lines.append(f"• [{r.run_id}] {r.label or r.agent_id} — {r.status} ({int(elapsed)}s)")
    return "Sub-agentes em background:\n" + "\n".join(lines)


def purge_old(max_age_seconds: float = 3600.0) -> int:
    """Remove runs finalizados há mais de max_age_seconds."""
    now = time.time()
    to_delete = [
        rid for rid, run in _runs.items()
        if run.ended_at and (now - run.ended_at) > max_age_seconds
    ]
    for rid in to_delete:
        del _runs[rid]
    return len(to_delete)
