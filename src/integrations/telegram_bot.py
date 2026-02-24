import os
import asyncio
import traceback
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moltyclaw import MoltyClaw
from rich.console import Console

console = Console()
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
agent = None

async def post_init(application: ApplicationBuilder) -> None:
    """Função executada após o bot no Telegram iniciar"""
    global agent
    console.print("[bold green]Inicializando navegador do MoltyClaw para o Telegram...[/bold green]")
    agent = MoltyClaw(name="MoltyClaw (Telegram)")
    await agent.init_browser()
    console.print("[bold green]Navegador ligado e pronto para pesquisas![/bold green]")
    
    bot = application.bot
    bot_info = await bot.get_me()
    console.print(f"[bold blue]🤖 MoltyClaw conectado no Telegram como @{bot_info.username}![/bold blue]")

async def stop_agent() -> None:
    global agent
    if agent:
        console.print("[bold yellow]Desligando navegador...[/bold yellow]")
        await agent.close_browser()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    
    user_text = ""
    if update.message.text:
        user_text = update.message.text.strip()
    elif update.message.voice or update.message.audio:
        audio_file = update.message.voice or update.message.audio
        file = await context.bot.get_file(audio_file.file_id)
        
        import time
        from pathlib import Path
        temp_dir = Path("temp")
        temp_dir.mkdir(exist_ok=True)
        file_path = temp_dir / f"telegram_audio_{int(time.time())}.ogg"
        await file.download_to_drive(file_path)
        
        console.print("[info]🎧 Áudio do Telegram recebido, transcrevendo...[/info]")
        transcribed = await agent.transcribe_audio(str(file_path))
        if transcribed:
            user_text = f"(Áudio Transcrito do Usuário): '{transcribed}'"
            console.print(f"[bold yellow]Transcrição:[/] {transcribed}")
        else:
            user_text = "(Áudio Recebido, ininteligível)"
            
    if not user_text:
        return

    # Evita que o bot responda a si mesmo (raro no telegram, mas por prevenção)
    if update.message.from_user.is_bot:
        return

    allowed_users = os.getenv("TELEGRAM_ALLOWED_USERS", "")
    if allowed_users.strip():
        allowed_list = [u.strip() for u in allowed_users.split(",")]
        user_id = str(update.message.from_user.id)
        username = update.message.from_user.username or ""
        if user_id not in allowed_list and username.replace("@", "") not in [u.replace("@", "") for u in allowed_list]:
            console.print(f"[bold yellow][Segurança] Ignorando Telegram de não autorizado: {username} ({user_id})[/bold yellow]")
            return

    is_group = update.message.chat.type in ['group', 'supergroup']
    
    # Se for um grupo, o bot só responde se for mencionado com @moltyclaw (ou se responderem a ele)
    if is_group:
        bot_username = context.bot.username
        if f"@{bot_username}" not in user_text and getattr(update.message.reply_to_message, 'from_user', None) and update.message.reply_to_message.from_user.username != bot_username:
            return
        # Limpa mencão do texto
        user_text = user_text.replace(f"@{bot_username}", "").strip()

    author = update.message.from_user.username or update.message.from_user.first_name
    console.print(f"\n[bold magenta]📩 Mensagem Telegram ({author}):[/bold magenta] {user_text}")

    # Envia o "Digitando..." no chat do Telegram
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    except:
        pass

    try:
        reply = await agent.ask(user_text)
        
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
        
        # Telegram tem limite de 4096 caracteres. Quebrando em chunks se necessário.
        if len(reply) > 4000:
            chunks = [reply[i:i+4000] for i in range(0, len(reply), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk)
            if media_path and os.path.exists(media_path):
                with open(media_path, 'rb') as f:
                    await update.message.reply_photo(photo=f)
        else:
            if media_path and os.path.exists(media_path):
                with open(media_path, 'rb') as f:
                    if reply:
                        await update.message.reply_photo(photo=f, caption=reply)
                    else:
                        await update.message.reply_photo(photo=f)
            elif reply:
                await update.message.reply_text(reply)
                
            if audio_reply_path and os.path.exists(audio_reply_path):
                with open(audio_reply_path, 'rb') as f:
                    await update.message.reply_voice(voice=f)
            
    except Exception as e:
        console.print(f"\n[bold red]Erro processando chat do Telegram: {e}[/bold red]\n{traceback.format_exc()}")
        await update.message.reply_text("🚨 Mals aí, fundi um pino aqui tentando processar sua mensagem! 🤖💥")

if __name__ == '__main__':
    if not TELEGRAM_TOKEN:
        console.print("[bold red]❌ ERRO: A variável TELEGRAM_TOKEN não foi encontrada no seu .env![/bold red]")
        console.print("[yellow]Fale com o @BotFather no Telegram para criar seu app e adicione o Token no .env![/yellow]")
    else:
        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        # Cria e constrói a aplicação do Telegram Python Bot
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

        # Monitora qualquer mensagem de texto que esbarre no bot
        app.add_handler(MessageHandler(filters.TEXT, handle_message))
        
        try:
            # Faz pooling ativo no Telegram
            app.run_polling()
        finally:
            # Correção para garantir que o Playwright fecha o Chrome ao encerrar
            if agent:
                asyncio.run(stop_agent())
