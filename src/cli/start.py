"""
MoltyClaw CLI — Start Bots
"""
import os
import sys
import time
import threading
from . import console, MOLTY_DIR, ensure_provider_api_key


def _get_color(name):
    if "WHATSAPP" in name or "NODE" in name:
        return "green"
    elif "DISCORD" in name:
        return "blue"
    elif "TELEGRAM" in name:
        return "cyan"
    elif "TWITTER" in name:
        return "blue"
    elif "BLUESKY" in name:
        return "bright_blue"
    return "cyan"


def _run_process(command, name):
    """Executa um subprocesso e repassa o log para o terminal principal."""
    import subprocess
    console.print(f"[bold {_get_color(name)}][{name}] Iniciando: {command}[/bold {_get_color(name)}]")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        env=env
    )

    for line in iter(process.stdout.readline, ''):
        sys.stdout.write(f"[{name}] {line}")
        sys.stdout.flush()

    process.stdout.close()
    return_code = process.wait()
    console.print(f"[bold red][{name}] Processo encerrado com código {return_code}[/bold red]")
    return process


def run_whatsapp():
    """Inicia o WhatsApp via AgentHub (processo único) + bridge Node.js."""
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from agent_hub import get_hub
    hub = get_hub()
    hub.start_integration("whatsapp")
    CMD_BRIDGE = f'node "{os.path.join(BASE_DIR, "src", "integrations", "whatsapp_bridge.js")}"'
    th_brg = threading.Thread(target=_run_process, args=(CMD_BRIDGE, "WHATSAPP-NODE"), daemon=True)
    time.sleep(2)
    th_brg.start()
    return [th_brg]


def run_discord():
    """Inicia o Discord via AgentHub (processo único)."""
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from agent_hub import get_hub
    hub = get_hub()
    hub.start_integration("discord")
    return []


def run_telegram():
    """Inicia o Telegram via AgentHub (processo único)."""
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from agent_hub import get_hub
    hub = get_hub()
    hub.start_integration("telegram")
    return []


def run_twitter():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    CMD_TWITTER = f'"{sys.executable}" "{os.path.join(BASE_DIR, "src", "integrations", "twitter_bot.py")}"'
    th_twt = threading.Thread(target=_run_process, args=(CMD_TWITTER, "TWITTER-BOT"), daemon=True)
    th_twt.start()
    return [th_twt]


def run_bluesky():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    CMD_BLUESKY = f'"{sys.executable}" "{os.path.join(BASE_DIR, "src", "integrations", "bluesky_bot.py")}"'
    th_bsky = threading.Thread(target=_run_process, args=(CMD_BLUESKY, "BLUESKY-BOT"), daemon=True)
    th_bsky.start()
    return [th_bsky]


def cli_start_bots(target):
    console.print(f"[bold magenta]Inicializando bots ({target}) em modo Bypass...[/bold magenta]")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)
    if not os.getenv("MOLTY_PROVIDER"):
        os.environ["MOLTY_PROVIDER"] = "mistral"

    _debug_provider = os.getenv('MOLTY_PROVIDER', 'mistral').lower()
    _debug_model_key = "OPENCODE_ZEN_MODEL" if _debug_provider == "opencode" else f"{_debug_provider.upper()}_MODEL"
    console.print(f"[dim]>> Provider carregado do .env: {_debug_provider}[/dim]")
    console.print(f"[dim]>> Modelo carregado: {os.getenv(_debug_model_key)}[/dim]")

    ensure_provider_api_key()

    active_threads = []

    if target == "all":
        os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
        os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
        os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
        os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
        os.environ["MOLTY_BLUESKY_ACTIVE"] = "1"
        active_threads.extend(run_whatsapp())
        time.sleep(1)
        active_threads.extend(run_discord())
        time.sleep(1)
        active_threads.extend(run_telegram())
        time.sleep(1)
        active_threads.extend(run_twitter())
        time.sleep(1)
        active_threads.extend(run_bluesky())
    elif target == "discord":
        os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
        active_threads.extend(run_discord())
    elif target == "whatsapp":
        os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
        active_threads.extend(run_whatsapp())
    elif target == "telegram":
        os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
        active_threads.extend(run_telegram())
    elif target == "bluesky":
        os.environ["MOLTY_BLUESKY_ACTIVE"] = "1"
        active_threads.extend(run_bluesky())
    else:
        console.print("[bold red]Alvo inválido! Use: discord, whatsapp, telegram, twitter, bluesky ou all[/bold red]")
        sys.exit(1)

    try:
        while True:
            time.sleep(1)
            if any(not t.is_alive() for t in active_threads):
                console.print("\n[bold red][!] Um dos processos essenciais desligou ou falhou.[/bold red]")
                break
    except KeyboardInterrupt:
        console.print("\n[bold yellow][!] Ctrl+C recebido! Desligando...[/bold yellow]")
    finally:
        sys.exit(0)
