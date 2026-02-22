import asyncio
import os
import traceback
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aiohttp import web
from moltyclaw import MoltyClaw
from rich.console import Console
from rich.panel import Panel

console = Console()
agent = None

async def init_moltyclaw(app):
    global agent
    console.print("[bold green]Inicializando MoltyClaw e instanciando o navegador interno...[/bold green]")
    agent = MoltyClaw()
    await agent.init_browser()
    console.print("[bold green]Agente MoltyClaw pronto na API HTTP![/bold green]")

async def cleanup_moltyclaw(app):
    global agent
    if agent:
        console.print("[bold yellow]Desligando o navegador do MoltyClaw...[/bold yellow]")
        await agent.close_browser()

async def handle_whatsapp_message(request):
    global agent
    try:
        data = await request.json()
        sender = data.get("sender", "Unknown")
        message = data.get("message", "")
        
        console.print(f"\n[bold blue]📩 Nova mensagem do WhatsApp ({sender}):[/bold blue] {message}")
        
        # Pede pro MoltyClaw responder (reaproveitamos tudo que ele ja tem de navegador/terminal)
        reply = await agent.ask(message)
        
        return web.json_response({"reply": reply})
    except Exception as e:
        console.print(f"[bold red]Erro processando mensagem: {e}[/bold red]\n{traceback.format_exc()}")
        return web.json_response({"reply": "Desculpe, tive um problema interno ao processar sua mensagem."}, status=500)

app = web.Application()
app.on_startup.append(init_moltyclaw)
app.on_cleanup.append(cleanup_moltyclaw)

app.router.add_post('/whatsapp', handle_whatsapp_message)

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🤖 MoltyClaw - Backend API para Integração (WhatsApp)[/bold cyan]\n"
        "[dim]Ouvindo chamadas POST em http://localhost:8080/whatsapp[/dim]",
        border_style="cyan"
    ))
    
    web.run_app(app, host='0.0.0.0', port=8080)
