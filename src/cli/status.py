"""
MoltyClaw CLI — Status & System Health Dashboard
Exibe um panorama completo e visual do agente, integrações, memória e recursos.
"""
import os
import sys
import re
import json
import shutil
import subprocess
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from . import console, MOLTY_DIR

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _get_provider_info(env_content: str):
    """Extrai informações do provider e modelo configurados."""
    provider_match = re.search(r'MOLTY_PROVIDER=(.*)', env_content)
    provider_id = provider_match.group(1).strip() if provider_match else "gemini"

    # Mapeamento de providers conhecidos
    provider_names = {
        "gemini": "Google Gemini",
        "mistral": "Mistral AI",
        "openrouter": "OpenRouter",
        "opencode": "OpenCode Zen",
        "kodacloud": "Koda Cloud",
        "ollama": "Ollama (Local)"
    }
    provider_name = provider_names.get(provider_id, provider_id.title())

    # Detecta modelo
    model_keys = {
        "gemini": "GEMINI_MODEL",
        "mistral": "MISTRAL_MODEL",
        "openrouter": "OPENROUTER_MODEL",
        "opencode": "OPENCODE_ZEN_MODEL",
        "kodacloud": "KODACLOUD_MODEL",
        "ollama": "OLLAMA_MODEL",
    }
    model_key = model_keys.get(provider_id, f"{provider_id.upper()}_MODEL")
    model_match = re.search(rf'{model_key}=(.*)', env_content)
    model_name = model_match.group(1).strip() if model_match else "Padrão"

    # Verifica status da API key correspondente
    key_names = {
        "gemini": "GEMINI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "opencode": "OPENCODE_ZEN_API_KEY",
        "kodacloud": None,
        "ollama": None,
    }
    target_key = key_names.get(provider_id)
    if target_key:
        key_match = re.search(rf'{target_key}=(.*)', env_content)
        key_val = key_match.group(1).strip() if key_match else ""
        key_status = "[bold green]Configurada[/bold green]" if key_val else "[bold red]Ausente[/bold red]"
    else:
        key_status = "[bold green]Local/Livre[/bold green]"

    return provider_name, provider_id, model_name, key_status


def _get_skills_stats():
    """Calcula estatísticas de skills."""
    try:
        from skills import load_skill_entries
        entries = load_skill_entries()
        total = len(entries)
        active = sum(1 for e in entries if e.eligible and e.enabled)
        disabled = sum(1 for e in entries if not e.enabled)
        ineligible = sum(1 for e in entries if not e.eligible and e.enabled)
        return total, active, disabled, ineligible
    except Exception:
        return 0, 0, 0, 0


def _get_mcp_stats():
    """Lê servidores MCP configurados."""
    mcp_config_paths = [
        os.path.join(MOLTY_DIR, "mcp_servers.json"),
        os.path.join(os.getcwd(), "mcp_servers.json"),
    ]
    for p in mcp_config_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    servers = data.get("mcpServers", {})
                    total = len(servers)
                    active = sum(1 for s in servers.values() if s.get("active", True) or not s.get("disabled", False))
                    return total, active
            except Exception:
                pass
    return 0, 0


def _get_channel_status(env_content: str):
    """Verifica quais canais de comunicação estão efetivamente configurados com credenciais."""
    configured = []

    def _has_val(pattern):
        m = re.search(pattern, env_content)
        if m:
            val = m.group(1).strip()
            return bool(val and not val.startswith("#"))
        return False

    # Discord (DISCORD_TOKEN ou DISCORD_BOT_TOKEN)
    if _has_val(r'DISCORD_(?:BOT_)?TOKEN=(.*)'):
        configured.append("[bold green]Discord[/bold green]")

    # Telegram (TELEGRAM_TOKEN ou TELEGRAM_BOT_TOKEN)
    if _has_val(r'TELEGRAM_(?:BOT_)?TOKEN=(.*)'):
        configured.append("[bold green]Telegram[/bold green]")

    # Bluesky (Handle + App Password)
    if _has_val(r'BLUESKY_HANDLE=(.*)') and (_has_val(r'BLUESKY_APP_PASSWORD=(.*)') or _has_val(r'BLUESKY_PASSWORD=(.*)')):
        configured.append("[bold green]Bluesky[/bold green]")

    # WhatsApp (requer Node.js + pasta de auth ou configurado)
    has_node = shutil.which("node") is not None
    w_auth_dir = os.path.join(os.getcwd(), ".wwebjs_auth")
    if has_node and (os.path.exists(w_auth_dir) or _has_val(r'WHATSAPP_ALLOWED_NUMBERS=(.*)')):
        configured.append("[bold green]WhatsApp[/bold green]")

    # Spotify
    if _has_val(r'SPOTIFY_CLIENT_ID=(.*)') and _has_val(r'SPOTIFY_CLIENT_SECRET=(.*)'):
        configured.append("[bold green]Spotify[/bold green]")

    # Gmail / Email
    if _has_val(r'GMAIL_USER=(.*)') and _has_val(r'GMAIL_APP_PASSWORD=(.*)'):
        configured.append("[bold green]Gmail[/bold green]")

    # Twitter / X
    if _has_val(r'TWITTER_BEARER_TOKEN=(.*)') or _has_val(r'TWITTER_API_KEY=(.*)'):
        configured.append("[bold green]Twitter[/bold green]")

    if not configured:
        return "[dim yellow]Nenhum configurado[/dim yellow]"

    return " • ".join(configured)


def _get_memory_stats():
    """Lê informações de persistência da memória."""
    mem_file = os.path.join(os.getcwd(), "MEMORY.md")
    if not os.path.exists(mem_file):
        mem_file = os.path.join(MOLTY_DIR, "MEMORY.md")

    mem_size = "0 KB"
    if os.path.exists(mem_file):
        size_bytes = os.path.getsize(mem_file)
        mem_size = f"{size_bytes / 1024:.1f} KB" if size_bytes > 0 else "0 KB"

    # Sessões
    sessions_dir = os.path.join(MOLTY_DIR, "sessions")
    session_count = 0
    if os.path.exists(sessions_dir):
        session_count = len([f for f in os.listdir(sessions_dir) if f.endswith(".json")])

    return mem_size, session_count


def cli_status():
    """Exibe o Dashboard Geral de Saúde e Status do MoltyClaw."""
    env_path = os.path.join(MOLTY_DIR, '.env')
    if not os.path.exists(env_path):
        env_path = os.path.join(os.getcwd(), '.env')

    env_content = ""
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                env_content = f.read()
        except Exception:
            pass

    # Coleta métricas
    provider_name, provider_id, model_name, key_status = _get_provider_info(env_content)
    skills_total, skills_active, skills_disabled, skills_ineligible = _get_skills_stats()
    mcp_total, mcp_active = _get_mcp_stats()
    channels = _get_channel_status(env_content)
    mem_size, session_count = _get_memory_stats()

    # Versão do sistema
    python_v = sys.version.split(" ")[0]
    mode = os.environ.get("MOLTY_MODE", "private")

    table = Table(
        show_header=True,
        header_style="bold #ff7700",
        box=None,
        padding=(0, 2),
        expand=True
    )
    table.add_column("Categoria", style="bold #ff8800", width=32)
    table.add_column("Detalhes & Diagnóstico", style="white")

    table.add_row("[bold #ff6600]🧠 Inteligência Artificial[/bold #ff6600]", "")
    table.add_row("  Provedor Ativo", f"[bold cyan]{provider_name}[/bold cyan] ({provider_id})")
    table.add_row("  Modelo Configurado", f"[yellow]{model_name}[/yellow]")
    table.add_row("  Status da API Key", key_status)
    table.add_row("", "")

    table.add_row("[bold #ff6600]🧩 Skills & Extensões[/bold #ff6600]", "")
    table.add_row(
        "  Total de Skills",
        f"[bold cyan]{skills_total}[/bold cyan] "
        f"([green]{skills_active} ativas[/green], "
        f"[dim red]{skills_disabled} desativadas[/dim red], "
        f"[yellow]{skills_ineligible} inelegíveis[/yellow])"
    )
    table.add_row("  Servidores MCP", f"[bold cyan]{mcp_total}[/bold cyan] configurados ({mcp_active} ativos)")
    table.add_row("", "")

    table.add_row("[bold #ff6600]📡 Canais & Memória[/bold #ff6600]", "")
    table.add_row("  Canais Configurados", channels)
    table.add_row("  Persistência (MEMORY.md)", f"[cyan]{mem_size}[/cyan]")
    table.add_row("  Histórico de Sessões", f"[cyan]{session_count}[/cyan] sessões salvas")
    table.add_row("", "")

    table.add_row("[bold #ff6600]⚙️ Ambiente & Execução[/bold #ff6600]", "")
    table.add_row("  Python Runtime", f"[dim]{python_v}[/dim]")
    table.add_row("  Modo do Agente", f"[green]{mode.upper()}[/green]")

    console.print(Panel(
        table,
        title="[bold #ff6600]⚡ MOLTYCLAW STATUS DASHBOARD ⚡[/bold #ff6600]",
        subtitle="[dim]Use moltyclaw -h para ver todos os comandos disponíveis[/dim]",
        border_style="#ff7700"
    ))
    sys.exit(0)
