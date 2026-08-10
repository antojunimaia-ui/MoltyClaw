"""
MoltyClaw CLI — Skills Management
"""
import os
import sys
from . import console, MOLTY_DIR, Panel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def cli_skill_list():
    from skills import load_skill_entries
    from rich.table import Table

    entries = load_skill_entries()
    if not entries:
        console.print("[bold yellow]⚠ Nenhuma skill encontrada.[/bold yellow]")
        sys.exit(0)

    table = Table(title="🧩 SKILLS DO MOLTYCLAW", border_style="cyan")
    table.add_column("Emoji", justify="center")
    table.add_column("Nome", style="cyan", no_wrap=True)
    table.add_column("Descrição", style="white")
    table.add_column("Fonte", style="dim")
    table.add_column("Status", justify="center")

    for e in sorted(entries, key=lambda x: x.name):
        status = "[bold green]✅ Ativo[/bold green]" if e.eligible else f"[bold red]❌ Inativo[/bold red]"
        source_color = "magenta" if e.source == "workspace" else ("blue" if e.source == "managed" else "dim")
        table.add_row(
            e.emoji,
            e.name,
            e.description[:60] + ("..." if len(e.description) > 60 else ""),
            f"[{source_color}]{e.source}[/{source_color}]",
            status
        )

    console.print(table)
    console.print("\n[dim]Use 'moltyclaw skill info <nome>' para mais detalhes.[/dim]")
    sys.exit(0)


def cli_skill_info(name):
    from skills import load_skill_entries, find_skill_by_name
    from rich.markdown import Markdown

    entries = load_skill_entries()
    skill = find_skill_by_name(entries, name)

    if not skill:
        console.print(f"[bold red]❌ Skill '{name}' não encontrada.[/bold red]")
        sys.exit(1)

    console.print(Panel.fit(
        f"[bold cyan]{skill.emoji} {skill.name.upper()}[/bold cyan]\n"
        f"[dim]{skill.description}[/dim]",
        border_style="cyan"
    ))

    console.print(f"\n[bold]📍 Caminho:[/bold] [dim]{skill.skill_dir}[/dim]")
    console.print(f"[bold]📦 Fonte:[/bold] [magenta]{skill.source}[/magenta]")

    status = "[bold green]✅ Elegível (Pronta para uso)[/bold green]" if skill.eligible else f"[bold red]❌ Inelegível: {skill.eligibility_reason}[/bold red]"
    console.print(f"[bold]⚖️ Status:[/bold] {status}")

    if skill.requires:
        console.print("\n[bold]⚙️ Requisitos:[/bold]")
        if skill.requires.get("bins"):
            console.print(f"  • Binários: [yellow]{', '.join(skill.requires['bins'])}[/yellow]")
        if skill.requires.get("env"):
            console.print(f"  • ENV Vars: [yellow]{', '.join(skill.requires['env'])}[/yellow]")

    try:
        with open(skill.skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
            console.print("\n[bold]📖 Conteúdo do SKILL.md:[/bold]")
            console.print(Markdown(content))
    except Exception:
        pass

    sys.exit(0)


def cli_skill_install(path):
    from skills import install_skill

    console.print(f"[bold cyan]📥 Instalando skill:[/bold cyan] {path}")
    success, msg = install_skill(path)
    if success:
        console.print(f"[bold green]✅ {msg}[/bold green]")
    else:
        console.print(f"[bold red]❌ Falha na instalação: {msg}[/bold red]")
    sys.exit(0 if success else 1)


def cli_skill_uninstall(name):
    from skills import uninstall_skill

    success, msg = uninstall_skill(name)
    if success:
        console.print(f"[bold green]✅ {msg}[/bold green]")
    else:
        console.print(f"[bold red]❌ {msg}[/bold red]")
    sys.exit(0 if success else 1)


def cli_skill_create(name):
    from skills import create_skill_scaffold

    console.print(f"[bold cyan]🛠️ Criando scaffold para nova skill:[/bold cyan] {name}")
    success, result = create_skill_scaffold(name, resources=["scripts", "references"])
    if success:
        console.print(f"[bold green]✅ Skill '{name}' criada com sucesso em:[/bold green] {result}")
        console.print(f"[dim]Edite o arquivo {os.path.join(result, 'SKILL.md')} para começar.[/dim]")
    else:
        console.print(f"[bold red]❌ {result}[/bold red]")
    sys.exit(0 if success else 1)


def cli_skill_package(path):
    from skills import package_skill

    console.print(f"[bold cyan]📦 Empacotando skill:[/bold cyan] {path}")
    success, result = package_skill(path)
    if success:
        console.print(f"[bold green]✅ Skill empacotada com sucesso em:[/bold green] {result}")
    else:
        console.print(f"[bold red]❌ {result}[/bold red]")
    sys.exit(0 if success else 1)


def cli_skill():
    """Dispatcher para subcomandos de skills."""
    if len(sys.argv) < 3:
        console.print("[bold red]Uso: moltyclaw skill list/info/install/uninstall/create/package <NOME|PATH>[/bold red]")
        sys.exit(1)

    sub = sys.argv[2].lower()
    if sub == "list":
        cli_skill_list()
    elif sub == "info" and len(sys.argv) >= 4:
        cli_skill_info(sys.argv[3])
    elif sub == "install" and len(sys.argv) >= 4:
        cli_skill_install(sys.argv[3])
    elif sub == "uninstall" and len(sys.argv) >= 4:
        cli_skill_uninstall(sys.argv[3])
    elif sub == "create" and len(sys.argv) >= 4:
        cli_skill_create(sys.argv[3])
    elif sub == "package" and len(sys.argv) >= 4:
        cli_skill_package(sys.argv[3])
    else:
        console.print("[bold red]Uso: moltyclaw skill list/info/install/uninstall/create/package <NOME|PATH>[/bold red]")
        sys.exit(1)
