import subprocess
import sys
import threading
import time
import os
import signal

# Usando as bibliotecas rich que já temos instaladas para um menu maravilhoso
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def run_process(command, name):
    """Executa um subprocesso e repassa o log para o terminal principal."""
    console.print(f"[bold {get_color(name)}][{name}] Iniciando: {command}[/bold {get_color(name)}]")
    
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

def get_color(name):
    if "WHATSAPP" in name or "NODE" in name:
        return "green"
    elif "DISCORD" in name:
        return "blue"
    elif "TELEGRAM" in name:
        return "cyan"
    return "cyan"

def run_whatsapp():
    CMD_SERVER = "python src/integrations/whatsapp_server.py"
    CMD_BRIDGE = "node src/integrations/whatsapp_bridge.js"
    
    th_svr = threading.Thread(target=run_process, args=(CMD_SERVER, "WHATSAPP-SVR"), daemon=True)
    th_brg = threading.Thread(target=run_process, args=(CMD_BRIDGE, "WHATSAPP-NODE"), daemon=True)
    
    th_svr.start()
    time.sleep(3) 
    th_brg.start()
    return [th_svr, th_brg]

def run_discord():
    CMD_DISCORD = "python src/integrations/discord_bot.py"
    th_dsc = threading.Thread(target=run_process, args=(CMD_DISCORD, "DISCORD-BOT"), daemon=True)
    th_dsc.start()
    return [th_dsc]

def run_telegram():
    CMD_TELEGRAM = "python src/integrations/telegram_bot.py"
    th_tel = threading.Thread(target=run_process, args=(CMD_TELEGRAM, "TELEGRAM-BOT"), daemon=True)
    th_tel.start()
    return [th_tel]

if __name__ == "__main__":
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🚀 INICIALIZADOR DO MOLTYCLAW 🚀[/bold cyan]\n"
        "[dim]Escolha qual módulo de inteligência você quer acordar hoje.[/dim]",
        border_style="cyan"
    ))
    
    console.print("1. [bold green]WhatsApp[/bold green] (Abre Server Python + Bridge Node.js)")
    console.print("2. [bold blue]Discord[/bold blue] (Abre Bot Discord)")
    console.print("3. [bold cyan]Telegram[/bold cyan] (Abre Bot Telegram)")
    console.print("4. [bold magenta]Todos[/bold magenta] (Acorda tudo de uma vez!)")
    console.print("5. [bold red]Sair[/bold red]\n")
    
    choice_str = Prompt.ask("Digite os números das suas escolhas (ex: 1 ou 1&&2)", default="1")
    
    active_threads = []
    
    choices = [c.strip() for c in choice_str.split("&&")]
    
    if "5" in choices:
        console.print("[dim]Desligando...[/dim]")
        sys.exit(0)
        
    if "4" in choices:
        active_threads.extend(run_whatsapp())
        time.sleep(1) # Intervalo seguro
        active_threads.extend(run_discord())
        time.sleep(1)
        active_threads.extend(run_telegram())
    else:
        if "1" in choices:
            active_threads.extend(run_whatsapp())
            time.sleep(1)
        if "2" in choices:
            active_threads.extend(run_discord())
            time.sleep(1)
        if "3" in choices:
            active_threads.extend(run_telegram())
            time.sleep(1)
        
    try:
        # Mantém script principal vivo monitorando as threads
        while True:
            time.sleep(1)
            # Verifica se as threads ativadas ainda vivem
            if any(not t.is_alive() for t in active_threads):
                console.print("\n[bold red][!] Um dos processos essenciais desligou ou falhou. Fechando o Launcher...[/bold red]")
                break
                
    except KeyboardInterrupt:
        console.print("\n[bold yellow][!] Ctrl+C recebido! Desligando os servidores e limpando processos...[/bold yellow]")
        
    finally:
        console.print("[bold cyan]Até logo![/bold cyan]")
        sys.exit(0)
