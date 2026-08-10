"""
MoltyClaw — Entry Point
Refatorado: todos os comandos CLI estão em src/cli/
"""
import subprocess
import sys
import os
import json
import time

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from src.initializer import initialize_moltyclaw, MOLTY_DIR
initialize_moltyclaw()

from src.cli import console, Panel, Prompt, HAS_QUESTIONARY, MOLTY_STYLE, ensure_provider_api_key
from src.cli.doctor import cli_doctor
from src.cli.config import cli_config
from src.cli.provider import cli_provider, cli_model
from src.cli.mcp import cli_mcp
from src.cli.organize import cli_organize, cli_organize_undo
from src.cli.skills import cli_skill
from src.cli.start import cli_start_bots
from src.cli.update import cli_update, cli_reset_memory
from src.cli.utils import cli_browser_toggle, cli_research, cli_onboard


def install_moltyclaw_path():
    scripts_dir = os.path.join(os.path.dirname(sys.executable), "Scripts")
    bat_path = os.path.join(scripts_dir, "moltyclaw.bat")
    exe_path = os.path.join(scripts_dir, "moltyclaw.exe")
    cwd = os.getcwd()
    bat_content = f'@echo off\ncd /d "{cwd}"\n"{sys.executable}" start_moltyclaw.py %*\n'

    try:
        if not os.path.exists(scripts_dir):
            os.makedirs(scripts_dir, exist_ok=True)

        if os.path.exists(exe_path):
            os.remove(exe_path)
            console.print("[dim]Antigo moltyclaw.exe removido para evitar conflitos.[/dim]")

        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        console.print(f"\n[bold green]✅ Sucesso! O comando 'moltyclaw' foi configurado e atualizado em:[/bold green] {bat_path}")
        console.print("[bold cyan]Agora você pode digitar 'moltyclaw' em qualquer terminal para iniciar o projeto de qualquer lugar![/bold cyan]\n")
    except Exception as e:
        console.print(f"\n[bold red]❌ Erro ao configurar o path:[/bold red] {e}\n")


def _show_help():
    console.print(Panel.fit(
        "[bold cyan]🚀 COMANDOS GLOBAIS DO MOLTYCLAW 🚀[/bold cyan]\n\n"
        "[dim]Modificadores globais: use [bold green]-m public[/bold green] (desativa terminal) ou [bold green]-m private[/bold green] antes de qualquer comando.[/dim]\n"
        "[green]moltyclaw[/green]                             : Abre o menu interativo padrão\n"
        "[green]moltyclaw web [--share][/green]               : Abre a WebUI imediatamente (exponha na rede com --share)\n"
        "[green]moltyclaw gateway[/green]                     : Inicia o Gateway FastAPI (só WebUI, sem integrações)\n"
        "[green]moltyclaw gateway --with <lista>[/green]      : Inicia o Gateway e já sobe as integrações indicadas\n"
        "[dim]                                          Exemplos: --with discord,telegram   --with all[/dim]\n"
        "[green]moltyclaw gateway --setup[/green]             : Abre seletor interativo de integrações antes de subir\n"
        "[green]moltyclaw gateway [--share][/green]           : Expõe o Gateway na rede (0.0.0.0) ao combinar com --share\n"
        "[green]moltyclaw start <ALVO>[/green]              : Inicia bots (discord, telegram, whatsapp, twitter, all) silenciosamente\n"
        "[green]moltyclaw update[/green]                      : Sincroniza com as atualizações mais recentes e instala libs via pip\n"
        "[green]moltyclaw --config[/green] ou [green]-c[/green]              : Abre seu arquivo .env no Bloco de Notas para edição amigável\n"
        "[green]moltyclaw doctor[/green]                      : Executa um diagnóstico de dependências (.env, Python, Node)\n"
        "[green]moltyclaw config set <CHAVE> <VALOR>[/green]  : Cria ou altera uma variável do `.env` por comando de linha\n"
        "[green]moltyclaw config get <CHAVE>[/green]          : Lê e devolve o valor de uma secret no seu `.env`\n"
        "[green]moltyclaw organize <PASTA>[/green]            : Organiza arquivos de uma bagunça instantaneamente usando LLM\n"
        "[green]moltyclaw organize --undo <PASTA>[/green]     : Desfaz a última organização usando o manifesto salvo\n"
        "[green]moltyclaw research \"<TEMA>\"[/green]           : Puxa um resumo web consolidado e rápido pro seu prompt\n"
        "[green]moltyclaw onboard[/green]                       : Inicia o assistente de configuração (Setup Wizard) guiado\n"
        "[green]moltyclaw reset memory[/green]                : Engatilha o protocolo de amnésia do agente esvaziando a MEMORY\n"
        "[green]moltyclaw mcp list/install/on/off[/green]      : Gerenciamento de Servidores MCP externos\n"
        "[green]moltyclaw provider[/green]                     : Seleciona e configura o provider de IA (Mistral, Gemini, OpenRouter, Ollama)\n"
        "[green]moltyclaw model[/green]                        : Seleciona o modelo de IA para o provider atual\n"
        "[green]moltyclaw skill list/info/create[/green]      : Gerenciamento do Sistema de Skills modulares\n"
        "[green]moltyclaw skill install <PATH>[/green]        : Instala uma skill a partir de pasta ou arquivo .skill\n"
        "[green]moltyclaw skill info <NOME>[/green]           : Detalhes, requisitos e manual de uma skill\n"
        "[green]moltyclaw browser headless=true/false[/green] : Ativa/Desativa o modo invisível do navegador\n"
        "[green]moltyclaw browser on/off[/green]              : Liga ou Desliga completamente o módulo de navegação\n"
        "[green]moltyclaw --help[/green] ou [green]-h[/green]                : Exibe este menu de ajuda",
        border_style="cyan"
    ))
    sys.exit(0)


def _setup_mode_flag():
    """Trata o modificador global -m / --mode."""
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


def _handle_gateway():
    """Lógica do subcomando gateway."""
    if "--share" in sys.argv:
        os.environ["MOLTY_WEBUI_SHARE"] = "1"

    if "--with" in sys.argv:
        with_idx = sys.argv.index("--with")
        try:
            with_val = sys.argv[with_idx + 1].lower().strip()
        except IndexError:
            console.print("[bold red]Uso: moltyclaw gateway --with <integrações>[/bold red]")
            console.print("[dim]Exemplo: moltyclaw gateway --with discord,telegram[/dim]")
            sys.exit(1)
        os.environ["MOLTY_GATEWAY_INTEGRATIONS"] = with_val
        console.print(f"[bold cyan]📡 Integrações para auto-start:[/bold cyan] {with_val}")

    elif "--setup" in sys.argv:
        _all = ["discord", "telegram", "whatsapp", "twitter", "bluesky"]
        _labels = {
            "whatsapp": "🟢  WhatsApp     — Server Python + Bridge Node.js",
            "discord":  "🔵  Discord      — Bot via API Oficial",
            "telegram": "✈️   Telegram     — Bot python-telegram-bot",
            "twitter":  "🐦  X / Twitter  — Bot API v2",
            "bluesky":  "🦋  Bluesky      — Bot AT Protocol (atproto)",
        }
        if HAS_QUESTIONARY:
            import questionary
            chosen = questionary.checkbox(
                "Integrações a ligar com o Gateway (Enter sem marcar = só WebUI):",
                choices=[questionary.Choice(_labels[p], value=p) for p in _all],
                style=MOLTY_STYLE,
                instruction="(↑↓ navegar  •  Espaço selecionar  •  Enter confirmar)",
            ).ask()
            if chosen is None:
                sys.exit(0)
        else:
            console.print("\n[bold cyan]Integrações para ligar com o Gateway:[/bold cyan]")
            for i, p in enumerate(_all, 1):
                console.print(f"{i}. {_labels[p]}")
            console.print("0. [bold white]Só a WebUI (sem integrações)[/bold white]")
            raw_in = Prompt.ask("Digite os números separados por vírgula (ex: 1,2)", default="0")
            mapping = {str(i + 1): p for i, p in enumerate(_all)}
            if raw_in.strip() == "0":
                chosen = []
            else:
                chosen = [mapping[c.strip()] for c in raw_in.split(",") if c.strip() in mapping]

        os.environ["MOLTY_GATEWAY_INTEGRATIONS"] = ",".join(chosen) if chosen else ""
        if chosen:
            console.print(f"[bold cyan]📡 Integrações selecionadas:[/bold cyan] {', '.join(chosen)}")
        else:
            console.print("[dim]ℹ️  Nenhuma integração selecionada — gateway só WebUI.[/dim]")

    console.print("[bold magenta]🔌 Iniciando MoltyClaw Gateway (FastAPI Hub)...[/bold magenta]")
    os.system("python src/webui/gateway.py")
    sys.exit(0)


def _interactive_menu():
    """Menu interativo principal."""
    console.clear()

    mcp_text = "[dim]Nenhum servidor MCP detectado.[/dim]"
    mcp_path = "mcp_servers.json"
    if os.path.exists(mcp_path):
        try:
            with open(mcp_path, "r", encoding='utf-8') as f:
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

    if HAS_QUESTIONARY:
        import questionary
        env_answer = questionary.select(
            "Ambiente Tático — selecione o modo:",
            choices=[
                questionary.Choice("🌐  WebUI Dashboard         (painel web em 127.0.0.1:5000)",      value="1"),
                questionary.Choice("🤖  Terminal & Conectores   (Discord, WhatsApp, Telegram…)",     value="2"),
                questionary.Choice("🔧  Configurar 'moltyclaw' Global  (adiciona atalho ao PATH)",   value="3"),
            ],
            style=MOLTY_STYLE,
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
        console.print("\n[bold yellow]⚠ AVISO IMPORTANTE:[/bold yellow]")
        console.print("Se você instalou o MoltyClaw através do comando [bold cyan]pip install moltyclaw[/bold cyan],")
        console.print("o atalho global já foi configurado automaticamente pelo Python e você JÁ PODE usar o comando 'moltyclaw' em qualquer terminal.\n")

        if HAS_QUESTIONARY:
            import questionary
            confirm = questionary.confirm(
                "Deseja prosseguir com a configuração manual do PATH mesmo assim?",
                default=False,
                style=MOLTY_STYLE,
            ).ask()
            if not confirm:
                sys.exit(0)
        else:
            confirm = Prompt.ask("[bold cyan]Deseja prosseguir com a configuração manual? [y/N][/bold cyan]", default="N")
            if confirm.lower() not in ["y", "s", "sim", "yes"]:
                sys.exit(0)

        install_moltyclaw_path()
        sys.exit(0)

    if env_choice == "1":
        if HAS_QUESTIONARY:
            import questionary
            share_answer = questionary.select(
                "🌐 Acesso remoto (Tailscale/celular/TV):",
                choices=[
                    questionary.Choice("🔒  Apenas local  (127.0.0.1:5000)",       value="n"),
                    questionary.Choice("📡  Expor na rede  (0.0.0.0 + IP local)",  value="y"),
                ],
                style=MOLTY_STYLE,
            ).ask()
            share = share_answer if share_answer else "n"
        else:
            share = Prompt.ask("🌐 Expor na rede? [y/N]", default="N")

        if share.lower() in ["y", "s", "sim", "yes", "1"]:
            os.environ["MOLTY_WEBUI_SHARE"] = "1"

        ensure_provider_api_key()
        os.system("python src/webui/app.py")
        sys.exit(0)

    # Terminal & Conectores
    if HAS_QUESTIONARY:
        import questionary
        connector_choices = questionary.checkbox(
            "Conectores a iniciar junto ao agente (Enter sem marcar = só terminal):",
            choices=[
                questionary.Choice("🟢  WhatsApp     — Server Python + Bridge Node.js",    value="whatsapp"),
                questionary.Choice("🔵  Discord      — Bot via API Oficial",                value="discord"),
                questionary.Choice("✈️   Telegram     — Bot python-telegram-bot",            value="telegram"),
                questionary.Choice("🐦  X / Twitter  — Bot API v2",                         value="twitter"),
                questionary.Choice("🦋  Bluesky      — Bot AT Protocol (atproto)",           value="bluesky"),
            ],
            style=MOLTY_STYLE,
            instruction="(↑↓ navegar  •  Espaço selecionar  •  Enter confirmar)",
        ).ask()

        if connector_choices is None:
            sys.exit(0)

        selected = set(connector_choices)
    else:
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
            selected = set()
        else:
            selected = {mapping[c] for c in raw if c in mapping}

    ensure_provider_api_key()

    if "whatsapp" in selected: os.environ["MOLTY_WHATSAPP_ACTIVE"] = "1"
    if "discord" in selected:  os.environ["MOLTY_DISCORD_ACTIVE"] = "1"
    if "telegram" in selected: os.environ["MOLTY_TELEGRAM_ACTIVE"] = "1"
    if "twitter" in selected:  os.environ["MOLTY_TWITTER_ACTIVE"] = "1"
    if "bluesky" in selected:  os.environ["MOLTY_BLUESKY_ACTIVE"] = "1"

    from src.cli.start import run_whatsapp, run_discord, run_telegram, run_twitter, run_bluesky

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

    import importlib.util, asyncio as _asyncio

    _molty_path = os.path.join(os.path.dirname(__file__), "src", "moltyclaw.py")
    _spec = importlib.util.spec_from_file_location("moltyclaw_main", _molty_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

    _asyncio.run(_mod.interactive_shell())
    sys.exit(0)


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)
    if not os.getenv("MOLTY_PROVIDER"):
        os.environ["MOLTY_PROVIDER"] = "mistral"

    _setup_mode_flag()

    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()

        if arg in ["--config", "-c"]:
            console.print("[bold cyan]📝 Abrindo arquivo .env para configuração...[/bold cyan]")
            env_path = os.path.join(MOLTY_DIR, '.env')
            os.system(f'notepad "{env_path}"')
            sys.exit(0)
        elif arg == "web":
            import webbrowser
            host, port = "127.0.0.1", 5000
            url = f"http://{host}:{port}"
            console.print(f"[bold magenta]🌐 Abrindo MoltyClaw WebUI em {url}...[/bold magenta]")
            webbrowser.open(url)
            sys.exit(0)
        elif arg == "gateway":
            _handle_gateway()
        elif arg == "doctor":
            cli_doctor()
            sys.exit(0)
        elif arg == "config":
            cli_config()
        elif arg == "mcp":
            cli_mcp()
        elif arg == "provider":
            cli_provider()
        elif arg == "model":
            cli_model()
        elif arg == "browser" and len(sys.argv) >= 3:
            cli_browser_toggle(sys.argv[2])
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
            cli_research(" ".join(sys.argv[2:]))
        elif arg == "onboard":
            cli_onboard()
        elif arg == "skill":
            cli_skill()
        elif arg in ["--help", "-h"]:
            _show_help()

    _interactive_menu()


if __name__ == "__main__":
    main()
