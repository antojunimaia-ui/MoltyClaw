import subprocess
import sys
import threading
import time
import os
import signal
import json

MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")
os.makedirs(MOLTY_DIR, exist_ok=True)
MOLTY_MCP_DIR = os.path.join(MOLTY_DIR, "mcp_modules")
os.makedirs(MOLTY_MCP_DIR, exist_ok=True)

# Usando as bibliotecas rich que já temos instaladas para um menu maravilhoso
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

try:
    import questionary
    from questionary import Style as QStyle
    HAS_QUESTIONARY = True
except ImportError:
    HAS_QUESTIONARY = False

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
    elif "BLUESKY" in name:
        return "bright_blue"
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

def run_bluesky():
    CMD_BLUESKY = "python src/integrations/bluesky_bot.py"
    th_bsky = threading.Thread(target=run_process, args=(CMD_BLUESKY, "BLUESKY-BOT"), daemon=True)
    th_bsky.start()
    return [th_bsky]

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
                
                # Check model
                import re
                model_match = re.search(r'MISTRAL_MODEL=(.*)', content)
                model_name = model_match.group(1).strip() if model_match else "mistral-medium (padrão)"
                console.print(f"[bold cyan]ℹ[/bold cyan] Modelo Mistral: [yellow]{model_name}[/yellow]")
            else:
                console.print("[bold yellow]⚠[/bold yellow] Chave MISTRAL_API_KEY ausente.")

            if 'GEMINI_API_KEY=' in content:
                console.print("[bold green]✔[/bold green] Chave do Gemini configurada.")
                import re
                model_match = re.search(r'GEMINI_MODEL=(.*)', content)
                model_name = model_match.group(1).strip() if model_match else "gemini-1.5-flash (padrão)"
                console.print(f"[bold cyan]ℹ[/bold cyan] Modelo Gemini: [yellow]{model_name}[/yellow]")
            else:
                console.print("[bold yellow]⚠[/bold yellow] Chave GEMINI_API_KEY ausente.")
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
            sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao ler mcp_servers.json:[/bold red] {e}")
        sys.exit(1)

def cli_mcp_uninstall(name):
    mcp_json_path = os.path.join(os.getcwd(), 'mcp_servers.json')
    if os.path.exists(mcp_json_path):
        with open(mcp_json_path, 'r', encoding='utf-8') as f:
            mcp_data = json.load(f)
        removed = False
        if name in mcp_data.get("mcpServers", {}):
            del mcp_data["mcpServers"][name]
            removed = True
        if name in mcp_data.get("disabledMcpServers", {}):
            del mcp_data["disabledMcpServers"][name]
            removed = True
        if removed:
            with open(mcp_json_path, 'w', encoding='utf-8') as f:
                json.dump(mcp_data, f, indent=2)
            console.print(f"[bold green]✅ '{name}' removido do mcp_servers.json[/bold green]")
        else:
            console.print(f"[bold yellow]⚠ Servidor '{name}' não encontrado no JSON.[/bold yellow]")
            
    # Remove pasta
    target_dir = os.path.join(os.getcwd(), "mcp_modules", name)
    if os.path.exists(target_dir):
        import shutil
        try:
            shutil.rmtree(target_dir)
            console.print(f"[bold green]✅ Arquivos locais de '{name}' apagados com sucesso das pastas do PC.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ Erro ao apagar a pasta: {e}[/bold red]")
            
    sys.exit(0)

def cli_mcp_toggle(name, turn_on=True):
    mcp_json_path = os.path.join(os.getcwd(), 'mcp_servers.json')
    if not os.path.exists(mcp_json_path):
        console.print("[bold red]❌ Arquivo mcp_servers.json não encontrado.[/bold red]")
        sys.exit(1)
        
    with open(mcp_json_path, 'r', encoding='utf-8') as f:
        mcp_data = json.load(f)
        
    mcp_data.setdefault("mcpServers", {})
    mcp_data.setdefault("disabledMcpServers", {})
    
    if turn_on:
        if name in mcp_data["disabledMcpServers"]:
            mcp_data["mcpServers"][name] = mcp_data["disabledMcpServers"].pop(name)
            console.print(f"[bold green]✅ Servidor '{name}' ativado![/bold green]")
        elif name in mcp_data["mcpServers"]:
            console.print(f"[bold yellow]⚠ Servidor '{name}' já estava ativado.[/bold yellow]")
        else:
            console.print(f"[bold red]❌ Servidor '{name}' não encontrado.[/bold red]")
    else:
        if name in mcp_data["mcpServers"]:
            mcp_data["disabledMcpServers"][name] = mcp_data["mcpServers"].pop(name)
            console.print(f"[bold yellow]🔌 Servidor '{name}' desativado temporariamente.[/bold yellow]")
        elif name in mcp_data["disabledMcpServers"]:
            console.print(f"[bold yellow]⚠ Servidor '{name}' já estava desativado.[/bold yellow]")
        else:
            console.print(f"[bold red]❌ Servidor '{name}' não encontrado.[/bold red]")
            
    with open(mcp_json_path, 'w', encoding='utf-8') as f:
        json.dump(mcp_data, f, indent=2)
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
    console.print(f"[bold magenta]Inicializando bots ({target}) em modo Bypass...[/bold magenta]")
    os.environ["MOLTY_PROVIDER"] = "mistral" # Provider padrão
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

def cli_organize(path):
    import asyncio
    import json as _json
    from datetime import datetime
    from rich.table import Table

    path = os.path.abspath(path)
    console.print(Panel.fit(
        f"[bold cyan]🧹 MOLTYCLAW ORGANIZER[/bold cyan]\n"
        f"[dim]Pasta alvo:[/dim] [yellow]{path}[/yellow]",
        border_style="cyan"
    ))

    if not os.path.isdir(path):
        console.print(f"[bold red]❌ '{path}' não é um diretório válido.[/bold red]")
        sys.exit(1)

    # ── 1. Escaneia arquivos (ignora subpastas já existentes) ─────────────────
    entries = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isdir(full):
            continue  # pula diretórios
        try:
            stat = os.stat(full)
            ext = os.path.splitext(name)[1].lower()
            size_kb = round(stat.st_size / 1024, 1)
            mod_date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
            entries.append({
                "name": name,
                "ext": ext or "(sem extensão)",
                "size_kb": size_kb,
                "modified": mod_date
            })
        except Exception:
            entries.append({"name": name, "ext": "?", "size_kb": 0, "modified": "?"})

    if not entries:
        console.print("[bold yellow]⚠ Nenhum arquivo encontrado na pasta (apenas subpastas).[/bold yellow]")
        sys.exit(0)

    console.print(f"[bold green]📂 {len(entries)} arquivo(s) encontrado(s).[/bold green]")

    # ── 2. Pede ao LLM um plano de categorização JSON ─────────────────────────
    console.print("[dim]Consultando IA para montar o plano de organização...[/dim]")

    file_summary = "\n".join(
        f"  - {e['name']}  (ext: {e['ext']}, {e['size_kb']}KB, modificado: {e['modified']})"
        for e in entries
    )

    organize_prompt = f"""Você é um organizador de arquivos. Analise a lista de arquivos abaixo e retorne APENAS um JSON (sem markdown, sem explicação) com o plano de organização.

ARQUIVOS NA PASTA:
{file_summary}

REGRAS:
1. Agrupe por tipo lógico: Imagens, Documentos, Vídeos, Músicas, Código, Executáveis, Compactados, Outros, etc.
2. Use nomes de pasta em PORTUGUÊS, capitalizados (ex: "Imagens", "Documentos")
3. Cada arquivo deve aparecer EXATAMENTE uma vez

FORMATO DE RESPOSTA (JSON puro, nada mais):
{{
  "NomeDaPasta": ["arquivo1.ext", "arquivo2.ext"],
  "OutraPasta": ["arquivo3.ext"]
}}"""

    sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
    from moltyclaw import MoltyClaw

    plan = None

    async def get_plan():
        nonlocal plan
        bot = MoltyClaw("MoltyOrganizer")
        response = await bot.ask(organize_prompt, silent=True)
        await bot.close_browser()
        return response

    try:
        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        raw_response = asyncio.run(get_plan())

        # Tenta extrair JSON da resposta (tolera markdown code blocks)
        import re
        json_match = re.search(r'\{[\s\S]*\}', raw_response or "")
        if json_match:
            plan = _json.loads(json_match.group())
    except Exception as e:
        console.print(f"[bold yellow]⚠ IA não retornou JSON válido: {e}[/bold yellow]")

    # ── 3. Fallback: organização por extensão se o LLM falhou ─────────────────
    if not plan or not isinstance(plan, dict):
        console.print("[dim]Usando regras por extensão como fallback...[/dim]")
        ext_map = {
            "Imagens": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff", ".heic"},
            "Documentos": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"},
            "Vídeos": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
            "Músicas": {".mp3", ".wav", ".ogg", ".flac", ".aac", ".m4a", ".wma"},
            "Código": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".rs", ".go", ".rb", ".php", ".json", ".xml", ".yaml", ".yml", ".md", ".sh", ".bat", ".ps1"},
            "Executáveis": {".exe", ".msi", ".bat", ".cmd", ".com", ".app", ".dmg"},
            "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
        }
        plan = {}
        for e in entries:
            ext = e["ext"].lower()
            dest = "Outros"
            for folder, exts in ext_map.items():
                if ext in exts:
                    dest = folder
                    break
            plan.setdefault(dest, []).append(e["name"])

    # ── 4. Preview com tabela Rich ────────────────────────────────────────────
    category_colors = {
        "Imagens": "green", "Documentos": "blue", "Vídeos": "magenta",
        "Músicas": "cyan", "Código": "yellow", "Executáveis": "red",
        "Compactados": "bright_magenta", "Outros": "dim",
    }

    table = Table(title="📋 Plano de Organização", border_style="cyan", show_lines=True)
    table.add_column("📁 Pasta", style="bold", min_width=15)
    table.add_column("📄 Arquivos", min_width=40)
    table.add_column("Qtd", justify="center", min_width=4)

    total_planned = 0
    for folder, files in sorted(plan.items()):
        color = category_colors.get(folder, "white")
        file_list = "\n".join(f"  • {f}" for f in files)
        table.add_row(f"[{color}]{folder}[/{color}]", file_list, str(len(files)))
        total_planned += len(files)

    console.print(table)
    console.print(f"\n[bold]{total_planned} arquivo(s) serão movidos para {len(plan)} pasta(s).[/bold]")

    # ── 5. Confirmação ────────────────────────────────────────────────────────
    if HAS_QUESTIONARY:
        confirm = questionary.confirm(
            "Executar este plano de organização?",
            default=True
        ).ask()
        if not confirm:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)
    else:
        confirm = Prompt.ask("Executar? [S/n]", default="S")
        if confirm.lower() not in ["s", "sim", "y", "yes", ""]:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)

    # ── 6. Executa as movimentações ─────────────────────────────────────────
    import shutil
    import json as _json2
    from datetime import datetime as _dt2
    moved = 0
    errors = 0
    manifest_moves = []  # log de src → dst para undo

    for folder, files in plan.items():
        dest_dir = os.path.join(path, folder)
        os.makedirs(dest_dir, exist_ok=True)

        for fname in files:
            src = os.path.join(path, fname)
            dst = os.path.join(dest_dir, fname)

            if not os.path.exists(src):
                console.print(f"[dim yellow]⚠ Ignorando '{fname}' (não encontrado)[/dim yellow]")
                errors += 1
                continue

            # Evita conflito de nomes
            if os.path.exists(dst):
                base, ext = os.path.splitext(fname)
                counter = 1
                while os.path.exists(dst):
                    dst = os.path.join(dest_dir, f"{base} ({counter}){ext}")
                    counter += 1

            try:
                shutil.move(src, dst)
                manifest_moves.append({"from": src, "to": dst})
                moved += 1
            except Exception as e:
                console.print(f"[bold red]❌ Erro movendo '{fname}': {e}[/bold red]")
                errors += 1

    # ── 7. Salva manifesto para undo ───────────────────────────────────────
    manifest_path = os.path.join(path, ".moltyclaw_organize.json")
    manifest_data = {
        "timestamp": _dt2.now().isoformat(),
        "total_moved": moved,
        "folders_created": list(plan.keys()),
        "moves": manifest_moves
    }
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            _json2.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # não crítico

    # ── 8. Relatório final ────────────────────────────────────────────────
    console.print(f"\n[bold green]✅ Organização concluída![/bold green]")
    console.print(f"   📦 {moved} arquivo(s) movido(s)")
    if errors:
        console.print(f"   ⚠️  {errors} erro(s)/ignorado(s)")
    console.print(f"   📂 {len(plan)} pasta(s) criada(s) em [cyan]{path}[/cyan]")
    console.print(f"   🔄 Para desfazer: [bold cyan]moltyclaw organize --undo {path}[/bold cyan]")
    sys.exit(0)


def cli_organize_undo(path):
    import json as _json3
    import shutil
    from rich.table import Table

    path = os.path.abspath(path)
    manifest_path = os.path.join(path, ".moltyclaw_organize.json")

    console.print(Panel.fit(
        f"[bold yellow]⏪ MOLTYCLAW ORGANIZER — UNDO[/bold yellow]\n"
        f"[dim]Revertendo organização em:[/dim] [yellow]{path}[/yellow]",
        border_style="yellow"
    ))

    if not os.path.exists(manifest_path):
        console.print("[bold red]❌ Nenhum manifesto (.moltyclaw_organize.json) encontrado nesta pasta.[/bold red]")
        console.print("[dim]A pasta precisa ter sido organizada pelo MoltyClaw para poder desfazer.[/dim]")
        sys.exit(1)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = _json3.load(f)
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao ler manifesto: {e}[/bold red]")
        sys.exit(1)

    moves = manifest.get("moves", [])
    timestamp = manifest.get("timestamp", "?")
    folders = manifest.get("folders_created", [])

    if not moves:
        console.print("[bold yellow]⚠ Manifesto vazio — nada para desfazer.[/bold yellow]")
        sys.exit(0)

    # Preview
    table = Table(title=f"⏪ Undo — Organização de {timestamp}", border_style="yellow", show_lines=True)
    table.add_column("📁 De (atual)", min_width=30)
    table.add_column("📂 Para (original)", min_width=30)

    for m in moves:
        src_display = os.path.relpath(m["to"], path)
        dst_display = os.path.relpath(m["from"], path)
        table.add_row(f"[red]{src_display}[/red]", f"[green]{dst_display}[/green]")

    console.print(table)
    console.print(f"\n[bold]{len(moves)} arquivo(s) serão revertidos para a raiz.[/bold]")

    # Confirmação
    if HAS_QUESTIONARY:
        confirm = questionary.confirm(
            "Desfazer esta organização?",
            default=True
        ).ask()
        if not confirm:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)
    else:
        confirm = Prompt.ask("Desfazer? [S/n]", default="S")
        if confirm.lower() not in ["s", "sim", "y", "yes", ""]:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)

    # Reverte
    restored = 0
    errs = 0
    for m in moves:
        src = m["to"]    # onde está agora
        dst = m["from"]  # onde estava antes

        if not os.path.exists(src):
            console.print(f"[dim yellow]⚠ '{os.path.basename(src)}' não encontrado (já movido?)[/dim yellow]")
            errs += 1
            continue

        try:
            shutil.move(src, dst)
            restored += 1
        except Exception as e:
            console.print(f"[bold red]❌ Erro revertendo '{os.path.basename(src)}': {e}[/bold red]")
            errs += 1

    # Limpa pastas vazias criadas pelo organize
    cleaned = 0
    for folder_name in folders:
        folder_path = os.path.join(path, folder_name)
        if os.path.isdir(folder_path):
            try:
                remaining = os.listdir(folder_path)
                if not remaining:
                    os.rmdir(folder_path)
                    cleaned += 1
            except Exception:
                pass

    # Remove o manifesto
    try:
        os.remove(manifest_path)
    except Exception:
        pass

    console.print(f"\n[bold green]✅ Undo concluído![/bold green]")
    console.print(f"   🔄 {restored} arquivo(s) restaurado(s)")
    if cleaned:
        console.print(f"   🗑️  {cleaned} pasta(s) vazia(s) removida(s)")
    if errs:
        console.print(f"   ⚠️  {errs} erro(s)/ignorado(s)")
    sys.exit(0)


def cli_research(query):
    console.print(Panel.fit(f"[bold cyan]🔍 MOLTYCLAW RESEARCHER[/bold cyan]\n[dim]Tópico de Busca:[/dim] [yellow]{query}[/yellow]"))
    console.print("[dim]Acordando o Navegador Analítico e conectando à LLM...[/dim]")
    
    import asyncio
    sys.path.append(os.path.join(os.path.dirname(__file__), "src"))
    from moltyclaw import MoltyClaw
    
    async def run():
        bot = MoltyClaw("MoltyResearcher")
        prompt = f"Faça uma pesquisa extensa e minuciosa na internet sobre o tema: '{query}'. Use OPEN_BROWSER e DDG_SEARCH (ou GOTO/READ_PAGE). Leia artigos e quando terminar de consolidar a informação, me responda DE FORMA DIRETA (sem usar tags JSON) descrevendo todo o resumo super detalhado e as mudanças para que eu possa ler aqui no terminal. Não economize no resumo, seja didático."
        
        await bot.ask(prompt)
        await bot.close_browser()

    try:
        asyncio.run(run())
        console.print("\n[bold green]✅ Pesquisa e resumo concluídos pela IA![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Erro durante a pesquisa:[/bold red] {e}")
        
    sys.exit(0)


if __name__ == "__main__":
    # Tratamento global do modo (-m / --mode)
    if "-m" in sys.argv or "--mode" in sys.argv:
        try:
            idx = sys.argv.index("-m") if "-m" in sys.argv else sys.argv.index("--mode")
            mode = sys.argv[idx + 1].lower()
            if mode in ["private", "public"]:
                os.environ["MOLTY_MODE"] = mode
            else:
                console.print("[bold red]Modo inválido. Use 'private' ou 'public'.[/bold red]")
                sys.exit(1)
            sys.argv.pop(idx)
            sys.argv.pop(idx)
        except IndexError:
            console.print("[bold red]Especifique um modo (ex: -m public).[/bold red]")
            sys.exit(1)
    else:
        os.environ["MOLTY_MODE"] = "private"

    # Tratamento de Argumentos de Linha de Comando (CLI)
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["--config", "-c"]:
            console.print("[bold cyan]📝 Abrindo arquivo .env para configuração...[/bold cyan]")
            # No Windows, abre o notepad direto no arquivo
            os.system(f"notepad {os.path.join(os.getcwd(), '.env')}")
            sys.exit(0)
        elif arg == "web":
            if "--share" in sys.argv:
                os.environ["MOLTY_WEBUI_SHARE"] = "1"
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
            elif sys.argv[2].lower() == "uninstall" and len(sys.argv) >= 4:
                cli_mcp_uninstall(sys.argv[3])
            elif sys.argv[2].lower() == "off" and len(sys.argv) >= 4:
                cli_mcp_toggle(sys.argv[3], turn_on=False)
            elif sys.argv[2].lower() == "on" and len(sys.argv) >= 4:
                cli_mcp_toggle(sys.argv[3], turn_on=True)
            elif sys.argv[2].lower() == "list":
                cli_mcp_list()
            else:
                console.print("[bold red]Uso: moltyclaw mcp install/uninstall/on/off <NOME> ou moltyclaw mcp list[/bold red]")
                sys.exit(1)
        elif arg == "reset" and len(sys.argv) >= 3 and sys.argv[2].lower() == "memory":
            cli_reset_memory()
        elif arg == "update":
            cli_update()
        elif arg == "start" and len(sys.argv) >= 3:
            cli_start_bots(sys.argv[2].lower())
        elif arg == "organize" and len(sys.argv) >= 3:
            if sys.argv[2] == "--undo" and len(sys.argv) >= 4:
                cli_organize_undo(sys.argv[3])
            else:
                cli_organize(sys.argv[2])
        elif arg == "research" and len(sys.argv) >= 3:
            # Junta tudo porque o texto pode não ter vindo em aspas
            cli_research(" ".join(sys.argv[2:]))
        elif arg in ["--help", "-h"]:
            console.print(Panel.fit(
                "[bold cyan]🚀 COMANDOS GLOBAIS DO MOLTYCLAW 🚀[/bold cyan]\n\n"
                "[dim]Modificadores globais: use [bold green]-m public[/bold green] (desativa terminal) ou [bold green]-m private[/bold green] antes de qualquer comando.[/dim]\n"
                "[green]moltyclaw[/green]                             : Abre o menu interativo padrão\n"
                "[green]moltyclaw web [--share][/green]               : Abre a WebUI imediatamente (exponha na rede com --share)\n"
                "[green]moltyclaw start <ALVO>[/green]              : Inicia bots (discord, telegram, whatsapp, twitter, all) silenciosamente\n"
                "[green]moltyclaw update[/green]                      : Sincroniza com as atualizações mais recentes e instala libs via pip\n"
                "[green]moltyclaw --config[/green] ou [green]-c[/green]              : Abre seu arquivo .env no Bloco de Notas para edição amigável\n"
                "[green]moltyclaw doctor[/green]                      : Executa um diagnóstico de dependências (.env, Python, Node)\n"
                "[green]moltyclaw config set <CHAVE> <VALOR>[/green]  : Cria ou altera uma variável do `.env` por comando de linha\n"
                "[green]moltyclaw config get <CHAVE>[/green]          : Lê e devolve o valor de uma secret no seu `.env`\n"
                "[green]moltyclaw organize <PASTA>[/green]            : Organiza arquivos de uma bagunça instantaneamente usando LLM\n"
                "[green]moltyclaw organize --undo <PASTA>[/green]     : Desfaz a última organização usando o manifesto salvo\n"
                "[green]moltyclaw research \"<TEMA>\"[/green]           : Puxa um resumo web consolidado e rápido pro seu prompt\n"
                "[green]moltyclaw reset memory[/green]                : Engatilha o protocolo de amnésia do agente esvaziando a MEMORY\n"
                "[green]moltyclaw mcp list[/green]                  : Lista todos os servidores MCP instalados em uma tabela\n"
                "[green]moltyclaw mcp install <REPO>[/green]          : Puxa e configura um pacote MCP a partir de um link GitHub\n"
                "[green]moltyclaw mcp uninstall <NOME>[/green]        : Deleta um pacote MCP remotamente baixado e remove do JSON\n"
                "[green]moltyclaw mcp on/off <NOME>[/green]           : Ativa ou Desativa um servidor temporariamente sem excluí-lo\n"
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
    
    # ── Menu Principal ────────────────────────────────────────────────────────
    if HAS_QUESTIONARY:
        molty_style = QStyle([
            ('qmark',       'fg:#00d7ff bold'),
            ('question',    'bold'),
            ('answer',      'fg:#00d7ff bold'),
            ('pointer',     'fg:#00d7ff bold'),
            ('highlighted', 'fg:#00d7ff bold'),
            ('selected',    'fg:#00ff87'),
            ('separator',   'fg:#555555'),
            ('instruction', 'fg:#888888'),
        ])

        env_answer = questionary.select(
            "Ambiente Tático — selecione o modo:",
            choices=[
                questionary.Choice("🌐  WebUI Dashboard         (painel web em 127.0.0.1:5000)",      value="1"),
                questionary.Choice("🤖  Terminal & Conectores   (Discord, WhatsApp, Telegram…)",     value="2"),
                questionary.Choice("🔧  Configurar 'moltyclaw' Global  (adiciona atalho ao PATH)",   value="3"),
            ],
            style=molty_style,
            use_shortcuts=False,
        ).ask()

        if env_answer is None:
            sys.exit(0)
        env_choice = env_answer

    else:
        console.print("\n[bold yellow] Ambiente Tático:[/bold yellow]")
        console.print("1. [bold cyan]Modo WebUI Dashboard[/bold cyan]")
        console.print("2. [bold magenta]Modo Terminal & Conectores[/bold magenta]")
        console.print("3. [bold green]Configurar 'moltyclaw' Global[/bold green]")
        env_choice = Prompt.ask("Selecione", choices=["1", "2", "3"], default="2")

    if env_choice == "3":
        install_moltyclaw_path()
        sys.exit(0)

    # ── Provedor de IA ────────────────────────────────────────────────────────
    if HAS_QUESTIONARY:
        provider_answer = questionary.select(
            "Provedor de IA:",
            choices=[
                questionary.Choice("⚡  Mistral AI      (MISTRAL_API_KEY)",     value="1"),
                questionary.Choice("🌐  OpenRouter      (OPENROUTER_API_KEY)",  value="2"),
                questionary.Choice("♊  Google Gemini    (GEMINI_API_KEY)",      value="3"),
            ],
            style=molty_style,
        ).ask()
        provider_choice = provider_answer if provider_answer else "1"
    else:
        console.print("\n[bold yellow] Provedor de IA:[/bold yellow]")
        console.print("1. [bold cyan]Mistral AI[/bold cyan]")
        console.print("2. [bold magenta]OpenRouter[/bold magenta]")
        console.print("3. [bold blue]Google Gemini[/bold blue]")
        provider_choice = Prompt.ask("Selecione", choices=["1", "2", "3"], default="1")

    if provider_choice == "2":
        os.environ["MOLTY_PROVIDER"] = "openrouter"
    elif provider_choice == "3":
        os.environ["MOLTY_PROVIDER"] = "gemini"
    else:
        os.environ["MOLTY_PROVIDER"] = "mistral"

    # ── WebUI ─────────────────────────────────────────────────────────────────
    if env_choice == "1":
        if HAS_QUESTIONARY:
            share_answer = questionary.select(
                "🌐 Acesso remoto (Tailscale/celular/TV):",
                choices=[
                    questionary.Choice("🔒  Apenas local  (127.0.0.1:5000)",       value="n"),
                    questionary.Choice("📡  Expor na rede  (0.0.0.0 + IP local)",  value="y"),
                ],
                style=molty_style,
            ).ask()
            share = share_answer if share_answer else "n"
        else:
            share = Prompt.ask("🌐 Expor na rede? [y/N]", default="N")

        if share.lower() in ["y", "s", "sim", "yes", "1"]:
            os.environ["MOLTY_WEBUI_SHARE"] = "1"
        os.system("python src/webui/app.py")
        sys.exit(0)

    # ── Seleção de Conectores (multi-select com Espaço + Enter) ───────────────
    if HAS_QUESTIONARY:
        connector_choices = questionary.checkbox(
            "Conectores a iniciar junto ao agente (Enter sem marcar = só terminal):",
            choices=[
                questionary.Choice("🟢  WhatsApp     — Server Python + Bridge Node.js",    value="whatsapp"),
                questionary.Choice("🔵  Discord      — Bot via API Oficial",                value="discord"),
                questionary.Choice("✈️   Telegram     — Bot python-telegram-bot",            value="telegram"),
                questionary.Choice("🐦  X / Twitter  — Bot API v2",                         value="twitter"),
                questionary.Choice("🦋  Bluesky      — Bot AT Protocol (atproto)",           value="bluesky"),
            ],
            style=molty_style,
            instruction="(↑↓ navegar  •  Espaço selecionar  •  Enter confirmar)",
        ).ask()

        # None = Ctrl+C/Escape; lista vazia = entrou sem marcar nada (terminal puro)
        if connector_choices is None:
            sys.exit(0)

        selected = set(connector_choices)

    else:
        # Fallback numérico
        console.print("\n[bold cyan] Quais braços do agente deseja iniciar?[/bold cyan]")
        console.print("0. [bold white]Só o Terminal[/bold white] (sem conectores externos)")
        console.print("1. [bold green]WhatsApp[/bold green]")
        console.print("2. [bold blue]Discord[/bold blue]")
        console.print("3. [bold cyan]Telegram[/bold cyan]")
        console.print("4. [bold blue]X/Twitter[/bold blue]")
        console.print("5. [bold bright_blue]Bluesky 🦋[/bold bright_blue]")
        console.print("6. [bold magenta]Todos[/bold magenta]")
        console.print("7. [bold red]Sair[/bold red]\n")
        choice_str = Prompt.ask("Digite os números (ex: 0 ou 1&&2, Enter=só terminal)", default="0")
        raw = [c.strip() for c in choice_str.split("&&")]
        mapping = {"1": "whatsapp", "2": "discord", "3": "telegram", "4": "twitter", "5": "bluesky"}
        if "7" in raw:
            sys.exit(0)
        if "6" in raw:
            selected = set(mapping.values())
        elif "0" in raw:
            selected = set()  # só terminal
        else:
            selected = {mapping[c] for c in raw if c in mapping}


        
    # ── Prepara o ambiente ──────────────────────────────────────────────────
    if "whatsapp" in selected: os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
    if "discord" in selected:  os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
    if "telegram" in selected: os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
    if "twitter" in selected:  os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
    if "bluesky" in selected:  os.environ["MOLTY_BLUESKY_ACTIVE"] = "1"

    # ── Lança os conectores selecionados ──────────────────────────────────────
    active_threads = []

    if "whatsapp" in selected:
        active_threads.extend(run_whatsapp())
        time.sleep(1)
    if "discord" in selected:
        active_threads.extend(run_discord())
        time.sleep(1)
    if "telegram" in selected:
        active_threads.extend(run_telegram())
        time.sleep(1)
    if "twitter" in selected:
        active_threads.extend(run_twitter())
        time.sleep(1)
    if "bluesky" in selected:
        active_threads.extend(run_bluesky())
        time.sleep(1)

    # Sempre abre o Terminal — direto no processo (sem subprocess!)
    import importlib.util, asyncio as _asyncio

    _molty_path = os.path.join(os.path.dirname(__file__), "src", "moltyclaw.py")
    _spec = importlib.util.spec_from_file_location("moltyclaw_main", _molty_path)
    _mod  = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

    _asyncio.run(_mod.interactive_shell())
    sys.exit(0)

