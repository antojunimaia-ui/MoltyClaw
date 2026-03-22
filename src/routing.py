import os
import json

MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")
BINDINGS_FILE = os.path.join(MOLTY_DIR, "bindings.json")

def load_bindings():
    if not os.path.exists(BINDINGS_FILE):
        return []
    try:
        with open(BINDINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_bindings(bindings):
    with open(BINDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bindings, f, indent=4)

def resolve_agent(channel, account_id=None, peer_id=None, guild_id=None):
    """
    Resolve qual agent_id deve responder baseado no contexto.
    Simula o resolve-route.ts do OpenClaw.
    """
    bindings = load_bindings()
    
    # 1. Tenta match por Peer ID específico (Mensagem Direta ou Usuário específico)
    if peer_id:
        for b in bindings:
            m = b.get("match", {})
            if m.get("channel") == channel and m.get("peer_id") == peer_id:
                if not account_id or m.get("account_id") == account_id:
                    return b.get("agent_id")

    # 2. Tenta match por Guild/Servidor (Discord)
    if guild_id:
        for b in bindings:
            m = b.get("match", {})
            if m.get("channel") == channel and m.get("guild_id") == guild_id:
                return b.get("agent_id")

    # 3. Tenta match por Canal/Conta (ex: qualquer coisa vindo desse token de bot)
    for b in bindings:
        m = b.get("match", {})
        if m.get("channel") == channel:
            if not account_id or m.get("account_id") == account_id:
                # Se não houver peer/guild no binding, é um match genérico do canal
                if not m.get("peer_id") and not m.get("guild_id"):
                    return b.get("agent_id")

    # 4. Fallback: MoltyClaw Master
    return "MoltyClaw"
