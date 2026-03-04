import subprocess
import sys
import threading
import time
import os
import signal
import json

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
    elif "TWITTER" in name:
        return "blue"
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

def run_twitter():
    CMD_TWITTER = "python src/integrations/twitter_bot.py"
    th_twt = threading.Thread(target=run_process, args=(CMD_TWITTER, "TWITTER-BOT"), daemon=True)
    th_twt.start()
    return [th_twt]

def install_moltyclaw_path():
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    bat_path = os.path.join(scripts_dir, "moltyclaw.bat")
    exe_path = os.path.join(scripts_dir, "moltyclaw.exe")
    cwd = os.getcwd()
    bat_content = f'@echo off\ncd /d "{cwd}"\npython start_moltyclaw.py %*\n'
    
    try:
        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir, exist_ok=True)
            
        # Remove an old conflicting executable if it exists
        if os.path.exists(exe_path):
            os.remove(exe_path)
            console.print("[dim]Antigo moltyclaw.exe removido para evitar conflitos.[/dim]")
            
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        console.print(f"\n[bold green]✅ Sucesso! O comando 'moltyclaw' foi configurado e atualizado em:[/bold green] {bat_path}")
        console.print("[bold cyan]Agora você pode digitar 'moltyclaw' em qualquer terminal para iniciar o projeto de qualquer lugar![/bold cyan]\n")
    except Exception as e:
        console.print(f"\n[bold red]❌ Erro ao configurar o path:[/bold red] {e}\n")

def cli_doctor():
    console.print(Panel.fit("[bold cyan]🩺 DIAGNÓSTICO DO MOLTYCLAW[/bold cyan]"))
    
    # Check Python
    console.print(f"[bold green]✔[/bold green] Versão do Python: {sys.version.split(' ')[0]}")
    
    # Check Node.js
    try:
        node_v = subprocess.check_output("node -v", shell=True, text=True).strip()
        console.print(f"[bold green]✔[/bold green] Node.js detectado: {node_v}")
    except Exception:
        console.print("[bold red]❌[/bold red] Node.js: Não encontrado (O WhatsApp não funcionará).")
        
    # Check .env
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        console.print("[bold green]✔[/bold green] Arquivo .env encontrado.")
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'MISTRAL_API_KEY=' in content:
                console.print("[bold green]✔[/bold green] Chave da Mistral configurada.")
            else:
                console.print("[bold yellow]⚠[/bold yellow] Chave MISTRAL_API_KEY ausente.")
    else:
        console.print("[bold red]❌[/bold red] Arquivo .env ausente.")
    sys.exit(0)

def cli_config_set(key, value):
    env_path = os.path.join(os.getcwd(), '.env')
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
    sys.exit(0)

def cli_config_get(key):
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith(f"{key}="):
                    console.print(f"[bold cyan]{line.strip()}[/bold cyan]")
                    sys.exit(0)
    console.print(f"[bold yellow]⚠ Chave {key} não encontrada no .env[/bold yellow]")
    sys.exit(0)

def cli_mcp_install(repo):
    console.print(f"[bold cyan]📥 Inicializando download do pacote MCP:[/bold cyan] {repo}")
    
    if not repo.startswith("http"):
        repo = f"https://{repo}"
        
    repo_name = repo.split("/")[-1].replace(".git", "")
    target_dir = os.path.join(os.getcwd(), "mcp_modules", repo_name)
    
    if not os.path.exists("mcp_modules"):
        os.makedirs("mcp_modules")
        
    if os.path.exists(target_dir):
        console.print(f"[bold yellow]⚠ O repositório {repo_name} já existe localmente. Atualizando...[/bold yellow]")
        os.system(f"cd {target_dir} && git pull")
    else:
        console.print(f"[dim]Clonando repositório para {target_dir}...[/dim]")
        ret = os.system(f"git clone {repo} {target_dir}")
        if ret != 0:
            console.print("[bold red]❌ Falha ao clonar o repositório. Verifique a URL.[/bold red]")
            sys.exit(1)
            
    command = "node"
    args = []
    
    if os.path.exists(os.path.join(target_dir, "package.json")):
        console.print("[dim]Node.js detectado! Instalando dependências (npm install)...[/dim]")
        os.system(f"cd {target_dir} && npm install")
        
        if os.path.exists(os.path.join(target_dir, "tsconfig.json")):
             console.print("[dim]TypeScript detectado! Compilando (npm run build)...[/dim]")
             os.system(f"cd {target_dir} && npm run build")
             
        if os.path.exists(os.path.join(target_dir, "build", "index.js")):
            args = [os.path.join("mcp_modules", repo_name, "build", "index.js")]
        elif os.path.exists(os.path.join(target_dir, "dist", "index.js")):
            args = [os.path.join("mcp_modules", repo_name, "dist", "index.js")]
        else:
            args = [os.path.join("mcp_modules", repo_name, "index.js")]
            
    elif os.path.exists(os.path.join(target_dir, "requirements.txt")) or os.path.exists(os.path.join(target_dir, "pyproject.toml")):
        console.print("[dim]Python detectado! Instalando dependências (pip install)...[/dim]")
        if os.path.exists(os.path.join(target_dir, "requirements.txt")):
            os.system(f"pip install -r {os.path.join(target_dir, 'requirements.txt')}")
        command = "python"
        
        if os.path.exists(os.path.join(target_dir, "server.py")):
             args = [os.path.join("mcp_modules", repo_name, "server.py")]
        elif os.path.exists(os.path.join(target_dir, "main.py")):
             args = [os.path.join("mcp_modules", repo_name, "main.py")]
        elif os.path.exists(os.path.join(target_dir, "src", "server.py")):
             args = [os.path.join("mcp_modules", repo_name, "src", "server.py")]
        else:
             args = [os.path.join("mcp_modules", repo_name, "index.py")]
             
    else:
        console.print("[bold yellow]⚠ Não foi possível detectar a linguagem (Node/Python) para build automático.[/bold yellow]")
        
    mcp_json_path = os.path.join(os.getcwd(), "mcp_servers.json")
    mcp_data = {"mcpServers": {}}
    
    if os.path.exists(mcp_json_path):
        with open(mcp_json_path, 'r', encoding='utf-8') as f:
            try:
                mcp_data = json.load(f)
            except Exception:
                pass
                
    if "mcpServers" not in mcp_data:
        mcp_data["mcpServers"] = {}
        
    mcp_data["mcpServers"][repo_name] = {
        "command": command,
        "args": [a.replace("\\", "/") for a in args]
    }
    
    with open(mcp_json_path, 'w', encoding='utf-8') as f:
        json.dump(mcp_data, f, indent=2)
        
    console.print(f"[bold green]✅ Pacote '{repo_name}' instalado e configurado dinamicamente![/bold green]")
    console.print(f"[dim]A entrada de inicialização foi salva em mcp_servers.json. Edite os argumentos manualmente se necessário.[/dim]")
    sys.exit(0)

def cli_mcp_list():
    import json
    from rich.table import Table
    
    mcp_json_path = os.path.join(os.getcwd(), 'mcp_servers.json')
    if not os.path.exists(mcp_json_path):
        console.print("[bold yellow]⚠ Arquivo mcp_servers.json não encontrado. Nenhum servidor MCP instalado.[/bold yellow]")
        sys.exit(0)
        
    try:
        with open(mcp_json_path, 'r', encoding='utf-8') as f:
            mcp_data = json.load(f)
            servers = mcp_data.get("mcpServers", {})
            
            if not servers:
                console.print("[dim]Nenhum servidor MCP detectado no arquivo.[/dim]")
                sys.exit(0)
                
            table = Table(title="🔌 SERVIDORES MCP INSTALADOS", border_style="cyan")
            table.add_column("Nome do Servidor", style="cyan", no_wrap=True)
            table.add_column("Comando", style="green")
            table.add_column("Argumentos Principais", style="dim")
            
            for name, config in servers.items():
                cmd = config.get("command", "-")
                args = config.get("args", [])
                args_str = " ".join(args)[:50] + ("..." if len(" ".join(args)) > 50 else "")
                table.add_row(name, cmd, args_str)
                
            console.print(table)
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao ler mcp_servers.json:[/bold red] {e}")
        
    sys.exit(0)

def cli_reset_memory():
    mem_path = os.path.join(os.getcwd(), 'MEMORY.md')
    if os.path.exists(mem_path):
        with open(mem_path, 'w', encoding='utf-8') as f:
            f.write("# MEMORY\n\nA memória episódica do MoltyClaw foi redefinida. O Agente começará limpo.\n")
        console.print("[bold green]✅ MEMORY.md resetado com sucesso. O MoltyClaw sofrerá de amnésia produtiva na próxima vez.[/bold green]")
    else:
        console.print("[bold yellow]⚠ Arquivo MEMORY.md não existe, então nada foi apagado.[/bold yellow]")
    sys.exit(0)

def cli_update():
    console.print(Panel.fit("[bold cyan]🔄 ATUALIZAÇÃO DO MOLTYCLAW[/bold cyan]"))
    console.print("[dim]Puxando as novidades do repositório oficial...[/dim]")
    os.system("git pull")
    console.print("[dim]Verificando e instalando novas dependências...[/dim]")
    os.system("pip install -r requirements.txt")
    console.print("[bold green]✅ Atualização concluída com sucesso![/bold green]")
    sys.exit(0)

def cli_start_bots(target):
    console.print(f"[bold magenta]🚀 Inicializando bots ({target}) em modo Bypass...[/bold magenta]")
    os.environ["MOLTY_PROVIDER"] = "mistral" # Provider padrão
    active_threads = []
    
    if target == "all":
        os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
        os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
        os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
        os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
        active_threads.extend(run_whatsapp())
        time.sleep(1)
        active_threads.extend(run_discord())
        time.sleep(1)
        active_threads.extend(run_telegram())
        time.sleep(1)
        active_threads.extend(run_twitter())
    elif target == "discord":
        os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
        active_threads.extend(run_discord())
    elif target == "whatsapp":
        os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
        active_threads.extend(run_whatsapp())
    elif target == "telegram":
        os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
        active_threads.extend(run_telegram())
    elif target == "twitter":
        os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
        active_threads.extend(run_twitter())
    else:
        console.print("[bold red]Alvo inválido! Use: discord, whatsapp, telegram, twitter ou all[/bold red]")
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

if __name__ == "__main__":
    # Tratamento de Argumentos de Linha de Comando (CLI)
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--config", "-c"]:
            console.print("[bold cyan]📝 Abrindo arquivo .env para configuração...[/bold cyan]")
            # No Windows, abre o notepad direto no arquivo
            os.system(f"notepad {os.path.join(os.getcwd(), '.env')}")
            sys.exit(0)
        elif arg == "web":
            console.print("[bold magenta]🚀 Lançando WebUI em modo Bypass...[/bold magenta]")
            os.system("python src/webui/app.py")
            sys.exit(0)
        elif arg == "doctor":
            cli_doctor()
        elif arg == "config":
            if len(sys.argv) >= 4 and sys.argv[2].lower() == "set":
                cli_config_set(sys.argv[3], sys.argv[4])
            elif len(sys.argv) >= 4 and sys.argv[2].lower() == "get":
                cli_config_get(sys.argv[3])
            else:
                console.print("[bold red]Uso: moltyclaw config set <CHAVE> <VALOR> ou moltyclaw config get <CHAVE>[/bold red]")
                sys.exit(1)
        elif arg == "mcp" and len(sys.argv) >= 3:
            if sys.argv[2].lower() == "install" and len(sys.argv) >= 4:
                cli_mcp_install(sys.argv[3])
            elif sys.argv[2].lower() == "list":
                cli_mcp_list()
            else:
                console.print("[bold red]Uso: moltyclaw mcp install <REPO> ou moltyclaw mcp list[/bold red]")
                sys.exit(1)
        elif arg == "reset" and len(sys.argv) >= 3 and sys.argv[2].lower() == "memory":
            cli_reset_memory()
        elif arg == "update":
            cli_update()
        elif arg == "start" and len(sys.argv) >= 3:
            cli_start_bots(sys.argv[2].lower())
        elif arg in ["--help", "-h"]:
            console.print(Panel.fit(
                "[bold cyan]🚀 COMANDOS GLOBAIS DO MOLTYCLAW 🚀[/bold cyan]\n\n"
                "[green]moltyclaw[/green]                             : Abre o menu interativo padrão\n"
                "[green]moltyclaw web[/green]                         : Abre a WebUI imediatamente na porta 5000 ignorando o Menu\n"
                "[green]moltyclaw start <ALVO>[/green]              : Inicia bots (discord, telegram, whatsapp, twitter, all) silenciosamente\n"
                "[green]moltyclaw update[/green]                      : Sincroniza com as atualizações mais recentes e instala libs via pip\n"
                "[green]moltyclaw --config[/green] ou [green]-c[/green]              : Abre seu arquivo .env no Bloco de Notas para edição amigável\n"
                "[green]moltyclaw doctor[/green]                      : Executa um diagnóstico de dependências (.env, Python, Node)\n"
                "[green]moltyclaw config set <CHAVE> <VALOR>[/green]  : Cria ou altera uma variável do `.env` por comando de linha\n"
                "[green]moltyclaw config get <CHAVE>[/green]          : Lê e devolve o valor de uma secret no seu `.env`\n"
                "[green]moltyclaw reset memory[/green]                : Engatilha o protocolo de amnésia do agente esvaziando a MEMORY\n"
                "[green]moltyclaw mcp install <REPO>[/green]          : Tenta puxar dinamicamente e injetar um pacote MCP ao bot\n"
                "[green]moltyclaw mcp list[/green]                  : Lista todos os servidores MCP instalados em uma tabela\n"
                "[green]moltyclaw --help[/green] ou [green]-h[/green]                : Exibe este menu de ajuda",
                border_style="cyan"
            ))
            sys.exit(0)

    console.clear()
    
    mcp_text = "[dim]Nenhum servidor MCP detectado.[/dim]"
    mcp_path = "mcp_servers.json"
    if os.path.exists(mcp_path):
        try:
            with open(mcp_path, "r", encoding="utf-8") as f:
                mcp_data = json.load(f)
                servers = list(mcp_data.get("mcpServers", {}).keys())
                if servers:
                    mcp_text = f"[bold green]🔌 {len(servers)} Servidores MCP Detectados:[/bold green] [cyan]{', '.join(servers)}[/cyan]"
        except Exception:
            mcp_text = "[bold red]Erro ao ler mcp_servers.json[/bold red]"
            
    console.print(Panel.fit(
        f"[bold cyan]🚀 INICIALIZADOR DO MOLTYCLAW 🚀[/bold cyan]\n"
        f"[dim]Escolha qual módulo de inteligência você quer acordar hoje.[/dim]\n"
        f"{mcp_text}",
        border_style="cyan"
    ))
    
    console.print("\n[bold yellow] Ambiente Tático:[/bold yellow]")
    console.print("1. [bold cyan]Modo WebUI Dashboard[/bold cyan] (Painel Web em 127.0.0.1:5000)")
    console.print("2. [bold magenta]Modo Terminal & Conectores[/bold magenta] (Discord, Whats, Telegram, etc)")
    console.print("3. [bold green]Configurar 'moltyclaw' Global[/bold green] (Adiciona atalho ao PATH)")
    
    env_choice = Prompt.ask("Selecione o modo de inicialização", choices=["1", "2", "3"], default="2")
    
    if env_choice == "3":
        install_moltyclaw_path()
        sys.exit(0)
    
    console.print("\n[bold yellow] Escolha do Provedor de IA:[/bold yellow]")
    console.print("1. [bold cyan]Mistral AI[/bold cyan] (MISTRAL_API_KEY)")
    console.print("2. [bold magenta]OpenRouter[/bold magenta] (OPENROUTER_API_KEY)")
    
    provider_choice = Prompt.ask("Selecione o provedor", choices=["1", "2"], default="1")
    
    if provider_choice == "2":
        os.environ["MOLTY_PROVIDER"] = "openrouter"
    else:
        os.environ["MOLTY_PROVIDER"] = "mistral"
        
    if env_choice == "1":
        # Run local flask app mapping the GUI UI
        os.system("python src/webui/app.py")
        sys.exit(0)
        
    console.print("\n[bold cyan] Quais braços do agente deseja iniciar?[/bold cyan]")
    
    console.print("1. [bold green]WhatsApp[/bold green] (Abre Server Python + Bridge Node.js)")
    console.print("2. [bold blue]Discord[/bold blue] (Abre Bot Discord)")
    console.print("3. [bold cyan]Telegram[/bold cyan] (Abre Bot Telegram)")
    console.print("4. [bold blue]X/Twitter[/bold blue] (Abre Bot Twitter API v2)")
    console.print("5. [bold magenta]Todos[/bold magenta] (Acorda tudo de uma vez!)")
    console.print("6. [bold red]Sair[/bold red]\n")
    
    choice_str = Prompt.ask("Digite os números das suas escolhas (ex: 1 ou 1&&2)", default="1")
    
    active_threads = []
    
    choices = [c.strip() for c in choice_str.split("&&")]
    
    if "6" in choices:
        console.print("[dim]Desligando...[/dim]")
        sys.exit(0)
        
    if "5" in choices:
        os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
        os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
        os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
        os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
        active_threads.extend(run_whatsapp())
        time.sleep(1) # Intervalo seguro
        active_threads.extend(run_discord())
        time.sleep(1)
        active_threads.extend(run_telegram())
        time.sleep(1)
        active_threads.extend(run_twitter())
    else:
        if "1" in choices:
            os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
            active_threads.extend(run_whatsapp())
            time.sleep(1)
        if "2" in choices:
            os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
            active_threads.extend(run_discord())
            time.sleep(1)
        if "3" in choices:
            os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
            active_threads.extend(run_telegram())
            time.sleep(1)
        if "4" in choices:
            os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
            active_threads.extend(run_twitter())
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
