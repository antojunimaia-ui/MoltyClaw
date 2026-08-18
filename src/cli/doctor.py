"""
MoltyClaw CLI — Doctor (Diagnóstico)
"""
import os
import sys
import re
from . import console, MOLTY_DIR, Panel


def cli_doctor():
    console.print(Panel.fit("[bold cyan]🩺 DIAGNÓSTICO DO MOLTYCLAW[/bold cyan]"))

    console.print(f"[bold green]✔[/bold green] Versão do Python: {sys.version.split(' ')[0]}")

    try:
        import subprocess
        node_v = subprocess.check_output("node -v", shell=True, text=True).strip()
        console.print(f"[bold green]✔[/bold green] Node.js detectado: {node_v}")
    except Exception:
        console.print("[bold red]❌[/bold red] Node.js: Não encontrado (O WhatsApp não funcionará).")

    env_path = os.path.join(MOLTY_DIR, '.env')
    if os.path.exists(env_path):
        console.print("[bold green]✔[/bold green] Arquivo .env encontrado.")
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'MISTRAL_API_KEY=' in content:
                console.print("[bold green]✔[/bold green] Chave da Mistral configurada.")
                model_match = re.search(r'MISTRAL_MODEL=(.*)', content)
                model_name = model_match.group(1).strip() if model_match else "mistral-medium (padrão)"
                console.print(f"[bold cyan]ℹ[/bold cyan] Modelo Mistral: [yellow]{model_name}[/yellow]")
            else:
                console.print("[bold yellow]⚠[/bold yellow] Chave MISTRAL_API_KEY ausente.")

            if 'GEMINI_API_KEY=' in content:
                console.print("[bold green]✔[/bold green] Chave do Gemini configurada.")
                model_match = re.search(r'GEMINI_MODEL=(.*)', content)
                model_name = model_match.group(1).strip() if model_match else "gemini-2.5-flash (padrão)"
                console.print(f"[bold cyan]ℹ[/bold cyan] Modelo Gemini: [yellow]{model_name}[/yellow]")
            else:
                console.print("[bold yellow]⚠[/bold yellow] Chave GEMINI_API_KEY ausente.")

            if 'OPENCODE_ZEN_API_KEY=' in content:
                console.print("[bold green]✔[/bold green] Chave do OpenCode Zen configurada.")
                model_match = re.search(r'OPENCODE_ZEN_MODEL=(.*)', content)
                model_name = model_match.group(1).strip() if model_match else "deepseek-v4-flash-free (padrão)"
                console.print(f"[bold cyan]ℹ[/bold cyan] Modelo OpenCode Zen: [yellow]{model_name}[/yellow]")
    else:
        console.print("[bold red]❌[/bold red] Arquivo .env ausente.")
