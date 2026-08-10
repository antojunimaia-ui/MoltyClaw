"""
MoltyClaw CLI — File Organizer
"""
import os
import sys
import re
import json
import shutil
from datetime import datetime
from . import console, MOLTY_DIR, Panel, Prompt, HAS_QUESTIONARY, MOLTY_STYLE


def cli_organize(path):
    path = os.path.abspath(path)
    console.print(Panel.fit(
        f"[bold cyan]🧹 MOLTYCLAW ORGANIZER[/bold cyan]\n"
        f"[dim]Pasta alvo:[/dim] [yellow]{path}[/yellow]",
        border_style="cyan"
    ))

    if not os.path.isdir(path):
        console.print(f"[bold red]❌ '{path}' não é um diretório válido.[/bold red]")
        sys.exit(1)

    entries = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isdir(full):
            continue
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

    sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
    from moltyclaw import MoltyClaw

    plan = None

    async def get_plan():
        nonlocal plan
        bot = MoltyClaw("MoltyOrganizer")
        response = await bot.ask(organize_prompt, silent=True)
        await bot.close_browser()
        return response

    try:
        import asyncio
        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        raw_response = asyncio.run(get_plan())

        json_match = re.search(r'\{[\s\S]*\}', raw_response or "")
        if json_match:
            plan = json.loads(json_match.group())
    except Exception as e:
        console.print(f"[bold yellow]⚠ IA não retornou JSON válido: {e}[/bold yellow]")

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

    category_colors = {
        "Imagens": "green", "Documentos": "blue", "Vídeos": "magenta",
        "Músicas": "cyan", "Código": "yellow", "Executáveis": "red",
        "Compactados": "bright_magenta", "Outros": "dim",
    }

    from rich.table import Table
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

    if HAS_QUESTIONARY:
        import questionary
        confirm = questionary.confirm("Executar este plano de organização?", default=True, style=MOLTY_STYLE).ask()
        if not confirm:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)
    else:
        confirm = Prompt.ask("Executar? [S/n]", default="S")
        if confirm.lower() not in ["s", "sim", "y", "yes", ""]:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)

    moved = 0
    errors = 0
    manifest_moves = []

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

    manifest_path = os.path.join(path, ".moltyclaw_organize.json")
    manifest_data = {
        "timestamp": datetime.now().isoformat(),
        "total_moved": moved,
        "folders_created": list(plan.keys()),
        "moves": manifest_moves
    }
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    console.print(f"\n[bold green]✅ Organização concluída![/bold green]")
    console.print(f"   📦 {moved} arquivo(s) movido(s)")
    if errors:
        console.print(f"   ⚠️  {errors} erro(s)/ignorado(s)")
    console.print(f"   📂 {len(plan)} pasta(s) criada(s) em [cyan]{path}[/cyan]")
    console.print(f"   🔄 Para desfazer: [bold cyan]moltyclaw organize --undo {path}[/bold cyan]")
    sys.exit(0)


def cli_organize_undo(path):
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
        with open(manifest_path, "r", encoding='utf-8') as f:
            manifest = json.load(f)
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao ler manifesto: {e}[/bold red]")
        sys.exit(1)

    moves = manifest.get("moves", [])
    timestamp = manifest.get("timestamp", "?")
    folders = manifest.get("folders_created", [])

    if not moves:
        console.print("[bold yellow]⚠ Manifesto vazio — nada para desfazer.[/bold yellow]")
        sys.exit(0)

    from rich.table import Table
    table = Table(title=f"⏪ Undo — Organização de {timestamp}", border_style="yellow", show_lines=True)
    table.add_column("📁 De (atual)", min_width=30)
    table.add_column("📂 Para (original)", min_width=30)

    for m in moves:
        src_display = os.path.relpath(m["to"], path)
        dst_display = os.path.relpath(m["from"], path)
        table.add_row(f"[red]{src_display}[/red]", f"[green]{dst_display}[/green]")

    console.print(table)
    console.print(f"\n[bold]{len(moves)} arquivo(s) serão revertidos para a raiz.[/bold]")

    if HAS_QUESTIONARY:
        import questionary
        confirm = questionary.confirm("Desfazer esta organização?", default=True, style=MOLTY_STYLE).ask()
        if not confirm:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)
    else:
        confirm = Prompt.ask("Desfazer? [S/n]", default="S")
        if confirm.lower() not in ["s", "sim", "y", "yes", ""]:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)

    restored = 0
    errs = 0
    for m in moves:
        src = m["to"]
        dst = m["from"]

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
