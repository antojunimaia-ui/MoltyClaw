import os
import asyncio
import traceback
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from moltyclaw import MoltyClaw
from rich.console import Console
from config_loader import get_config
from initializer import MOLTY_DIR

console = Console()
load_dotenv(os.path.join(MOLTY_DIR, '.env'))

# Carrega do moltyclaw.json
molty_config = get_config()
t_cfg = molty_config.get("channels", {}).get("telegram", {})

TELEGRAM_TOKEN = t_cfg.get("bot_token") or os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED_USERS = t_cfg.get("allowed_users") or os.getenv("TELEGRAM_ALLOWED_USERS", "")

from routing import resolve_agent

agent_instances = {}

async def get_agent(agent_id):
    if agent_id in agent_instances:
        return agent_instances[agent_id]
    
    console.print(f"[dim]>> Criando instância dinâmica para o agente: {agent_id}[/dim]")
    new_agent = MoltyClaw(agent_id=agent_id)
    await new_agent.init_browser()
    if new_agent.mcp_hub:
        await new_agent.mcp_hub.connect_servers()
    
    agent_instances[agent_id] = new_agent
    return new_agent

async def post_init(application) -> None:
    # Apenas loga que o Gateway está pronto
    bot_info = await application.bot.get_me()
    console.print(f"[bold blue]🤖 Gateway Telegram conectado como @{bot_info.username}![/bold blue]")
    console.print("[dim]Aguardando mensagens para roteamento dinâmico...[/dim]")

async def stop_agent() -> None:
    for agent_id, agent in agent_instances.items():
        console.print(f"[bold yellow]Desligando navegador do agente {agent_id}...[/bold yellow]")
        await agent.close_browser()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message: return
    
    # Rota dinâmica baseado no OpenClaw Strategy
    peer_id = str(update.message.from_user.id)
    chat_id = str(update.message.chat.id)
    target_agent_id = resolve_agent(channel="telegram", peer_id=peer_id, guild_id=chat_id)
    target_agent = await get_agent(target_agent_id)

    # Se a mensagem tiver texto puro, extrai
    user_text = ""
    if update.message.text:
        user_text = update.message.text.strip()
    elif update.message.voice or update.message.audio:
        audio_file = update.message.voice or update.message.audio
        file = await context.bot.get_file(audio_file.file_id)
        
        import time
        from pathlib import Path
        temp_dir = Path(os.path.join(MOLTY_DIR, "temp"))
        temp_dir.mkdir(exist_ok=True)
        file_path = temp_dir / f"telegram_audio_{int(time.time())}.ogg"
        await file.download_to_drive(file_path)
        
        console.print(f"[info]🎧 Áudio do Telegram recebido para {target_agent_id}, transcrevendo...[/info]")
        transcribed = await target_agent.transcribe_audio(str(file_path))
        if transcribed:
            user_text = f"(Áudio Transcrito do Usuário): '{transcribed}'"
            console.print(f"[bold yellow]Transcrição:[/] {transcribed}")
        else:
            user_text = "(Áudio Recebido, ininteligível)"
            
    if not user_text and update.message.caption:
        user_text = update.message.caption.strip()

    if not user_text:
        return
        
    console.print(f"[debug] Incoming msg to {target_agent_id}: '{user_text[:50]}...' from '{update.message.from_user.username}' chat type: '{update.message.chat.type}'")

    # Evita que o bot responda a si mesmo (raro no telegram, mas por prevenção)
    if update.message.from_user.is_bot:
        return

    allowed_users = TELEGRAM_ALLOWED_USERS
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
        if not bot_username: return
        
        is_reply_to_bot = False
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            if update.message.reply_to_message.from_user.username == bot_username:
                is_reply_to_bot = True
                
        is_mentioned = f"@{bot_username.lower()}" in user_text.lower()
        
        if not is_mentioned and not is_reply_to_bot:
            return
            
        import re
        # Limpa menção do texto ignorando maiúsculas
        user_text = re.sub(f"(?i)@{bot_username}", "", user_text).strip()
        if not user_text:
            user_text = "Olá!"
            
        # Opcional: Se a pessoa também usar o nome do bot por extenso e virgula, a gente limpa
        user_text = re.sub(f"(?i)^{bot_username}[,\s]*", "", user_text).strip()

    author = update.message.from_user.username or update.message.from_user.first_name
    console.print(f"\n[bold magenta]📩 Mensagem Telegram ({author}):[/bold magenta] {user_text}")

    # Envia o "Digitando..." no chat do Telegram
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    except:
        pass

    # Callback de announce: sub-agentes em background usam isso pra mandar resultado de volta
    async def reply_callback(message: str):
        try:
            # Quebra em chunks se necessário (Telegram limita 4096 chars)
            for i in range(0, len(message), 4000):
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message[i:i+4000]
                )
        except Exception as _cb_err:
            console.print(f"[error]Erro no announce callback do sub-agente: {_cb_err}[/error]")

    try:
        reply = await target_agent.ask(user_text, reply_callback=reply_callback)

        
        import re
        media_path = None
        audio_reply_path = None
        
        match_img = re.search(r'\[SCREENSHOT_TAKEN:\s*(.*?)\]', reply)
        if match_img:
            media_path = match_img.group(1).strip()
            reply = reply.replace(match_img.group(0), "").strip()
            # Resolve path relativo para a pasta temp do agente
            if not os.path.isabs(media_path) and not os.path.exists(media_path):
                potential_path = os.path.join(target_agent.base_dir, "temp", media_path)
                if os.path.exists(potential_path):
                    media_path = potential_path
            
        match_aud = re.search(r'\[AUDIO_REPLY:\s*(.*?)\]', reply)
        if match_aud:
            audio_reply_path = match_aud.group(1).strip()
            reply = reply.replace(match_aud.group(0), "").strip()
            # Resolve path relativo para a pasta temp do agente
            if not os.path.isabs(audio_reply_path) and not os.path.exists(audio_reply_path):
                potential_path = os.path.join(target_agent.base_dir, "temp", audio_reply_path)
                if os.path.exists(potential_path):
                    audio_reply_path = potential_path
        
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
    import argparse
    parser = argparse.ArgumentParser(description="MoltyClaw Telegram Bot")
    parser.add_argument("--agent", type=str, help="ID do Agente para carregar", default="MoltyClaw")
    parser.add_argument("--name", type=str, help="Nome visível do bot", default=None)
    args = parser.parse_args()

    # Se for um sub-agente, tenta carregar o .env dele PRIMEIRO para sobrepor o token se necessário
    if args.agent != "MoltyClaw":
        agent_env = os.path.join(MOLTY_DIR, "agents", args.agent, ".env")
        if os.path.exists(agent_env):
            console.print(f"[dim]>> Carregando configurações específicas do agente '{args.agent}'...[/dim]")
            load_dotenv(agent_env, override=True)
            # Atualiza o token se ele existir no .env do agente
            TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_TOKEN

    if not TELEGRAM_TOKEN:
        console.print("[bold red]❌ ERRO: A variável TELEGRAM_TOKEN não foi encontrada no seu .env![/bold red]")
        console.print("[yellow]Fale com o @BotFather no Telegram para criar seu app e adicione o Token no .env![/yellow]")
    else:
        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        # Pega nome final
        bot_name = args.name if args.name else f"{args.agent} (Telegram)"
        
        # Injeta o factory de post_init com o agente correto
        async def agent_post_init(application):
            global agent
            console.print(f"[bold green]Inicializando navegador para o Agente '{args.agent}' no Telegram...[/bold green]")
            agent = MoltyClaw(name=bot_name, agent_id=args.agent)
            await agent.init_browser()
            if agent.mcp_hub:
                await agent.mcp_hub.connect_servers()
            bot_info = await application.bot.get_me()
            console.print(f"[bold blue]🤖 Agente '{args.agent}' conectado como @{bot_info.username}![/bold blue]")

        # Cria e constrói a aplicação do Telegram Python Bot
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(agent_post_init).build()

        # Monitora qualquer mensagem que não seja um comando slash (/)
        app.add_handler(MessageHandler(~filters.COMMAND, handle_message))
        
        try:
            # Faz pooling ativo no Telegram
            app.run_polling()
        finally:
            # Correção para garantir que o Playwright fecha o Chrome ao encerrar
            if agent:
                asyncio.run(stop_agent())
