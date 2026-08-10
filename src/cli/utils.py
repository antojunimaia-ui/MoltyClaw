"""
MoltyClaw CLI — Browser Toggle, Research, Onboard
"""
import os
import sys
import json
from . import console, MOLTY_DIR, Panel


def cli_browser_toggle(arg):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    arg_lower = arg.lower()
    config_path = os.path.join(MOLTY_DIR, "moltyclaw.json")
    from config_loader import get_config
    molty_cfg = get_config()

    if "browser" not in molty_cfg:
        molty_cfg["browser"] = {}

    if "headless=" in arg_lower:
        is_headless = "true" in arg_lower
        molty_cfg["browser"]["headless"] = is_headless
        status = "[bold green]ATIVADO[/bold green] (Invisível)" if is_headless else "[bold yellow]DESATIVADO[/bold yellow] (Visível)"
        console.print(f"✅ Modo Headless {status} no arquivo de configuração!")
    elif arg_lower in ["on", "off"]:
        is_enabled = arg_lower == "on"
        molty_cfg["browser"]["enabled"] = is_enabled
        status = "[bold green]LIGADO[/bold green]" if is_enabled else "[bold red]DESLIGADO[/bold red]"
        console.print(f"✅ Navegador {status} com sucesso! (A IA não verá ferramentas de web se estiver desligado)")
    else:
        if arg_lower in ["true", "false"]:
            is_headless = "true" in arg_lower
            molty_cfg["browser"]["headless"] = is_headless
            console.print(f"✅ Modo Headless atualizado para {is_headless}!")
        else:
            console.print("[bold red]Argumento inválido. Use headless=true|false ou on|off.[/bold red]")
            sys.exit(1)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(molty_cfg, f, indent=4)
    sys.exit(0)


def cli_research(query):
    console.print(Panel.fit(f"[bold cyan]🔍 MOLTYCLAW RESEARCHER[/bold cyan]\n[dim]Tópico de Busca:[/dim] [yellow]{query}[/yellow]"))
    console.print("[dim]Acordando o Navegador Analítico e conectando à LLM...[/dim]")

    import asyncio
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from moltyclaw import MoltyClaw

    async def run():
        bot = MoltyClaw("MoltyResearcher", agent_id="MoltyClaw")
        prompt = f"Faça uma pesquisa minuciosa na internet sobre o tema: '{query}'. ATENÇÃO: Você DEVE usar a tag <tool> com JSON para chamar a ferramenta DDG_SEARCH (e GOTO se precisar ler algo) AGORA MESMO para buscar as informações. Somente DEPOIS de obter os resultados, você deve dar a resposta final detalhada."

        await bot.ask(prompt)
        await bot.close_browser()

    try:
        asyncio.run(run())
        console.print("\n[bold green]✅ Pesquisa e resumo concluídos pela IA![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Erro durante a pesquisa:[/bold red] {e}")

    sys.exit(0)


def cli_onboard():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import onboarding
    onboarding.run_onboarding()
