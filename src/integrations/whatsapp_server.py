import asyncio
import os
import traceback
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import aiohttp
from aiohttp import web
from agent_hub import get_hub
from rich.console import Console
from rich.panel import Panel

console = Console()

# Hub compartilhado — mesma instância do agente usada pela WebUI, Discord, Telegram...
hub = get_hub()


async def handle_whatsapp_message(request):
    try:
        data = await request.json()
        sender_name = data.get("sender", "Unknown")
        sender_id = data.get("sender_id", sender_name)
        message = data.get("message", "")

        console.print(f"\n[bold blue]📩 Nova mensagem do WhatsApp ({sender_name}):[/bold blue] {message}")

        # Transcrição de áudio se for um arquivo de áudio
        if message and message.startswith("[AUDIO_FILE: ") and message.endswith("]"):
            media_path = message.replace("[AUDIO_FILE: ", "").replace("]", "").strip()
            if os.path.exists(media_path):
                console.print(f"[info]🎧 Áudio detectado, extraindo texto via Voxtral API...[/info]")
                transcribed = hub.transcribe_audio_sync(media_path)
                if transcribed:
                    message = f"(Áudio Transcrito do Usuário): '{transcribed}'"
                    console.print(f"[bold yellow]Transcrição:[/] {transcribed}")
                else:
                    message = "(Áudio enviado pelo usuário, mas ininteligível ou falha na transcrição)"

        # Exibe as Tools chamadas pelo MoltyClaw no WhatsApp (igual à WebUI),
        # disparando pelo bridge na porta 8081
        async def tool_callback(msg: str):
            try:
                async with aiohttp.ClientSession() as sess:
                    async with sess.post(
                        "http://localhost:8081/send_whatsapp",
                        json={"to": sender_id, "message": f"⚙️ {msg}"},
                        timeout=10,
                    ) as resp:
                        await resp.read()
            except Exception:
                pass

        reply = await hub.ask(
            message,
            channel="whatsapp",
            peer_id=sender_id,
            peer_name=sender_name,
            tool_callback=tool_callback,
        )

        import re
        media_path = None
        audio_reply_path = None

        match_img = re.search(r'\[SCREENSHOT_TAKEN:\s*(.*?)\]', reply)
        if match_img:
            media_path = match_img.group(1)
            reply = reply.replace(match_img.group(0), "").strip()

        match_aud = re.search(r'\[AUDIO_REPLY:\s*(.*?)\]', reply)
        if match_aud:
            audio_reply_path = match_aud.group(1)
            reply = reply.replace(match_aud.group(0), "").strip()

        response_data = {"reply": reply}
        if media_path and os.path.exists(media_path):
            response_data["media"] = os.path.abspath(media_path)
        if audio_reply_path and os.path.exists(audio_reply_path):
            response_data["audio_reply"] = os.path.abspath(audio_reply_path)

        return web.json_response(response_data)

    except Exception as e:
        console.print(f"[bold red]Erro processando mensagem: {e}[/bold red]\n{traceback.format_exc()}")
        return web.json_response(
            {"reply": "Desculpe, tive um problema interno ao processar sua mensagem."},
            status=500
        )


app = web.Application()
app.router.add_post('/whatsapp', handle_whatsapp_message)

if __name__ == '__main__':
    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🤖 MoltyClaw - Backend API para Integração (WhatsApp)[/bold cyan]\n"
        "[dim]Conectado ao AgentHub compartilhado — ouvindo em http://localhost:8080/whatsapp[/dim]",
        border_style="cyan"
    ))

    web.run_app(app, host='0.0.0.0', port=8080)
