"""
MoltyClaw CLI — MCP Server Management
"""
import os
import sys
import json
import shutil
from . import console, MOLTY_DIR, Panel, Prompt

MOLTY_MCP_DIR = os.path.join(MOLTY_DIR, "mcp_modules")


def cli_mcp_install(repo):
    console.print(f"[bold cyan]📥 Inicializando download do pacote MCP:[/bold cyan] {repo}")

    if not repo.startswith("http"):
        repo = f"https://{repo}"

    repo_name = repo.split("/")[-1].replace(".git", "")
    target_dir = os.path.join(MOLTY_MCP_DIR, repo_name)

    if not os.path.exists(MOLTY_MCP_DIR):
        os.makedirs(MOLTY_MCP_DIR)

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
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "build", "index.js")]
        elif os.path.exists(os.path.join(target_dir, "dist", "index.js")):
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "dist", "index.js")]
        else:
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "index.js")]

    elif os.path.exists(os.path.join(target_dir, "requirements.txt")) or os.path.exists(os.path.join(target_dir, "pyproject.toml")):
        console.print("[dim]Python detectado! Instalando dependências (pip install)...[/dim]")
        if os.path.exists(os.path.join(target_dir, "requirements.txt")):
            os.system(f"pip install -r {os.path.join(target_dir, 'requirements.txt')}")
        command = sys.executable

        if os.path.exists(os.path.join(target_dir, "server.py")):
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "server.py")]
        elif os.path.exists(os.path.join(target_dir, "main.py")):
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "main.py")]
        elif os.path.exists(os.path.join(target_dir, "src", "server.py")):
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "src", "server.py")]
        else:
            args = [os.path.join(MOLTY_MCP_DIR, repo_name, "index.py")]
    else:
        console.print("[bold yellow]⚠ Não foi possível detectar a linguagem (Node/Python) para build automático.[/bold yellow]")

    mcp_json_path = os.path.join(MOLTY_DIR, "mcp_servers.json")
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
    from rich.table import Table

    mcp_json_path = os.path.join(MOLTY_DIR, 'mcp_servers.json')
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
    mcp_json_path = os.path.join(MOLTY_DIR, 'mcp_servers.json')
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

    target_dir = os.path.join(MOLTY_MCP_DIR, name)
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            console.print(f"[bold green]✅ Arquivos locais de '{name}' apagados com sucesso das pastas do PC.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ Erro ao apagar a pasta: {e}[/bold red]")

    sys.exit(0)


def cli_mcp_toggle(name, turn_on=True):
    mcp_json_path = os.path.join(MOLTY_DIR, 'mcp_servers.json')
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


def cli_mcp():
    """Dispatcher para subcomandos MCP."""
    if len(sys.argv) >= 4 and sys.argv[2].lower() == "install":
        cli_mcp_install(sys.argv[3])
    elif len(sys.argv) >= 4 and sys.argv[2].lower() == "uninstall":
        cli_mcp_uninstall(sys.argv[3])
    elif len(sys.argv) >= 4 and sys.argv[2].lower() == "off":
        cli_mcp_toggle(sys.argv[3], turn_on=False)
    elif len(sys.argv) >= 4 and sys.argv[2].lower() == "on":
        cli_mcp_toggle(sys.argv[3], turn_on=True)
    elif len(sys.argv) >= 3 and sys.argv[2].lower() == "list":
        cli_mcp_list()
    else:
        console.print("[bold red]Uso: moltyclaw mcp install/uninstall/on/off <NOME> ou moltyclaw mcp list[/bold red]")
        sys.exit(1)
