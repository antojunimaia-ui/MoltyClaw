"""
MoltyClaw CLI — Update & Reset Memory
"""
import os
import sys
import json
from . import console, MOLTY_DIR, Panel, Prompt, HAS_QUESTIONARY, MOLTY_STYLE

try:
    import questionary
except ImportError:
    questionary = None


def cli_update():
    import urllib.request
    from rich.table import Table
    from rich.markdown import Markdown

    GITHUB_REPO = "antojunimaia-ui/MoltyClaw"
    RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
    VERSION_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'VERSION')

    console.print(Panel.fit("[bold cyan]🔄 ATUALIZAÇÃO DO MOLTYCLAW[/bold cyan]"))

    local_version = "desconhecida"
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            local_version = f.read().strip()

    console.print(f"[dim]Versão local instalada:[/dim] [bold cyan]{local_version}[/bold cyan]")
    console.print(f"[dim]Consultando releases em github.com/{GITHUB_REPO}...[/dim]\n")

    try:
        req = urllib.request.Request(RELEASES_API)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "MoltyClaw-Updater")
        with urllib.request.urlopen(req, timeout=10) as response:
            releases = json.loads(response.read().decode())
    except Exception as e:
        console.print(f"[bold yellow]⚠ Falha ao consultar GitHub Releases: {e}[/bold yellow]")
        console.print("[dim]Realizando git pull como fallback...[/dim]")
        os.system("git pull")
        os.system("pip install -r requirements.txt")
        console.print("[bold green]✅ Atualização via fallback concluída![/bold green]")
        sys.exit(0)

    if not releases:
        console.print("[bold yellow]⚠ Nenhuma release encontrada no repositório.[/bold yellow]")
        sys.exit(0)

    latest = releases[0]
    latest_tag = latest.get("tag_name", "?")
    latest_name = latest.get("name", latest_tag)
    published_at = latest.get("published_at", "?")[:10]
    body = latest.get("body", "Sem notas de release.")
    is_prerelease = latest.get("prerelease", False)

    clean_local = local_version.lstrip("v").strip()
    clean_remote = latest_tag.lstrip("v").strip()

    if clean_local == clean_remote:
        console.print(Panel.fit(
            f"[bold green]✅ Você já está na versão mais recente![/bold green]\n"
            f"[dim]Local: {local_version} │ Remota: {latest_tag}[/dim]",
            border_style="green"
        ))
        sys.exit(0)

    tag_style = "[bold yellow]PRE-RELEASE[/bold yellow] " if is_prerelease else ""
    console.print(Panel.fit(
        f"[bold cyan]🆕 Nova versão disponível![/bold cyan]\n\n"
        f"[dim]Sua versão:[/dim]    [bold red]{local_version}[/bold red]\n"
        f"[dim]Disponível:[/dim]    [bold green]{latest_tag}[/bold green] {tag_style}\n"
        f"[dim]Nome:[/dim]          {latest_name}\n"
        f"[dim]Publicado em:[/dim]  {published_at}",
        border_style="cyan"
    ))

    console.print("\n[bold]📋 Changelog:[/bold]")
    try:
        console.print(Markdown(body))
    except Exception:
        console.print(f"[dim]{body[:500]}[/dim]")

    if len(releases) > 1:
        table = Table(title="📦 Últimas Releases", border_style="dim")
        table.add_column("Tag", style="cyan", no_wrap=True)
        table.add_column("Nome", style="white")
        table.add_column("Data", style="dim")
        table.add_column("Tipo", style="yellow")
        for r in releases[:5]:
            r_type = "🧪 Pre-release" if r.get("prerelease") else "✅ Estável"
            table.add_row(r.get("tag_name", "?"), r.get("name", "?"), r.get("published_at", "?")[:10], r_type)
        console.print(table)

    console.print("")
    if HAS_QUESTIONARY:
        import questionary
        confirm = questionary.confirm(f"Atualizar de {local_version} → {latest_tag}?", default=True, style=MOLTY_STYLE).ask()
        if not confirm:
            console.print("[dim]Atualização cancelada.[/dim]")
            sys.exit(0)
    else:
        confirm = Prompt.ask(f"Atualizar de {local_version} → {latest_tag}? [S/n]", default="S")
        if confirm.lower() not in ["s", "sim", "y", "yes", ""]:
            console.print("[dim]Atualização cancelada.[/dim]")
            sys.exit(0)

    console.print("\n[dim]Puxando as novidades do repositório oficial...[/dim]")
    os.system("git pull")
    console.print("[dim]Verificando e instalando novas dependências...[/dim]")
    os.system("pip install -r requirements.txt")

    try:
        with open(VERSION_FILE, 'w', encoding='utf-8') as f:
            f.write(latest_tag)
        console.print(f"[dim]Arquivo VERSION atualizado para {latest_tag}[/dim]")
    except Exception:
        pass

    console.print(f"\n[bold green]✅ Atualização concluída! Agora você está na versão {latest_tag}.[/bold green]")
    sys.exit(0)


def cli_reset_memory():
    mem_path = os.path.join(MOLTY_DIR, "workspace", 'MEMORY.md')
    if os.path.exists(mem_path):
        with open(mem_path, 'w', encoding='utf-8') as f:
            f.write("# MEMORY\n\nA memória episódica do MoltyClaw foi redefinida. O Agente começará limpo.\n")
        console.print("[bold green]✅ MEMORY.md resetado com sucesso. O MoltyClaw sofrerá de amnésia produtiva na próxima vez.[/bold green]")
    else:
        console.print("[bold yellow]⚠ Arquivo MEMORY.md não existe, então nada foi apagado.[/bold yellow]")
    sys.exit(0)
