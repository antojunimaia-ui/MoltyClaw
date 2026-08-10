"""
MoltyClaw CLI — Helpers Compartilhados
"""
import os
import sys
import json
import re
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.theme import Theme

try:
    import questionary
    from questionary import Style as QStyle
    HAS_QUESTIONARY = True
except ImportError:
    HAS_QUESTIONARY = False

MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "moltyclaw": "bold green",
    "user": "bold blue"
})
console = Console(theme=custom_theme)

MOLTY_STYLE = QStyle([
    ('qmark', 'fg:#00d7ff bold'),
    ('question', 'bold'),
    ('answer', 'fg:#00d7ff bold'),
    ('pointer', 'fg:#00d7ff bold'),
    ('highlighted', 'fg:#00d7ff bold'),
    ('selected', 'fg:#00ff87'),
    ('separator', 'fg:#555555'),
    ('instruction', 'fg:#888888'),
]) if HAS_QUESTIONARY else None


def ensure_provider_api_key():
    """Garante que o provider atual tenha sua API key configurada."""
    from dotenv import load_dotenv
    load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)

    provider = os.getenv("MOLTY_PROVIDER", "mistral").lower()

    key_providers = {
        "mistral":    ("MISTRAL_API_KEY",     "https://console.mistral.ai/"),
        "gemini":     ("GEMINI_API_KEY",      "https://aistudio.google.com/apikey"),
        "openrouter": ("OPENROUTER_API_KEY",  "https://openrouter.ai/keys"),
        "opencode":   ("OPENCODE_ZEN_API_KEY", "https://opencode.ai/auth"),
    }

    if provider not in key_providers:
        return

    env_key, url = key_providers[provider]
    current = os.getenv(env_key, "").strip()
    if current:
        return

    console.print(f"\n[bold yellow]⚠ API Key não configurada para o provider '{provider}'.[/bold yellow]")
    console.print(f"[dim]Obtenha sua chave em: {url}[/dim]")

    api_key = Prompt.ask(f"\n Cole sua {env_key}")

    if not api_key.strip():
        console.print("[bold yellow]⚠ Nenhuma chave informada. O agente tentará iniciar mesmo assim (pode cair no fallback).[/bold yellow]")
        return

    env_path = os.path.join(MOLTY_DIR, '.env')
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    found = False
    with open(env_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith(f"{env_key}="):
                f.write(f"{env_key}={api_key.strip()}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"\n{env_key}={api_key.strip()}\n")
    os.environ[env_key] = api_key.strip()
    console.print(f"[bold green]✅ API Key salva no .env para '{provider}'.[/bold green]")


def config_set(key, value):
    """Cria ou altera uma variável no .env"""
    env_path = os.path.join(MOLTY_DIR, '.env')
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

    found = False
    with open(env_path, 'w', encoding='utf-8') as f:
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"\n{key}={value}\n")

    console.print(f"[bold green]✅ Configuração salva no .env:[/bold green] {key}={value}")


def config_get(key):
    """Lê um valor do .env"""
    env_path = os.path.join(MOLTY_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith(f"{key}="):
                    console.print(f"[bold cyan]{line.strip()}[/bold cyan]")
                    return
    console.print(f"[bold yellow]⚠ Chave {key} não encontrada no .env[/bold yellow]")
