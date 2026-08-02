import os
import asyncio
import traceback
import discord
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent_hub import get_hub
from initializer import MOLTY_DIR
import aiohttp
import socket

# Correção para o aiohttp no Windows com Python 3.10+ (Evita travamentos do aiohappyeyeballs e TimeoutError de IPv6)
_orig_tcp_init = aiohttp.TCPConnector.__init__
def _new_tcp_init(self, *args, **kwargs):
    kwargs['family'] = socket.AF_INET
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _new_tcp_init

from rich.console import Console
from config_loader import get_config

console = Console()
load_dotenv(os.path.join(MOLTY_DIR, '.env'), override=True)

# Carrega do moltyclaw.json
molty_config = get_config()
d_cfg = molty_config.get("channels", {}).get("discord", {})

DISCORD_TOKEN = d_cfg.get("bot_token") or os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
DISCORD_ALLOWED_USERS = d_cfg.get("allowed_users") or os.getenv("DISCORD_ALLOWED_USERS", "")

# Hub compartilhado — mesma instância do agente usada pela WebUI e outros canais
hub = get_hub()


class MoltyClawDiscordBot(discord.Client):
    def __init__(self, *args, **kwargs):
        self.name = kwargs.pop('name', 'DiscordGateway')
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        console.print("[bold green]Discord conectado ao AgentHub compartilhado (aguardando mensagens)...[/bold green]")

    async def on_ready(self):
        console.print(f"[bold blue]🤖 Discord conectado como {self.user}![/bold blue]")
        await self.change_presence(activity=discord.Game(name="MoltyClaw — Agente Único 🖥️"))

    async def on_message(self, message):
        try:
            # Ignora mensagens enviadas pelo próprio bot (previne loops infinitos)
            if message.author == self.user:
                return
                
            allowed_users = DISCORD_ALLOWED_USERS
            if allowed_users.strip():
                allowed_list = [u.strip() for u in allowed_users.split(",")]
                if str(message.author.id) not in allowed_list:
                    console.print(f"[bold yellow][Segurança] Ignorando Discord de não autorizado: {message.author} ({message.author.id})[/bold yellow]")
                    return
                
            # CHECAGEM DO COMANDO DE ENTRAR E SAIR DA CALL
            if message.content.lower().startswith('!call'):
                if not hasattr(message.author, 'voice') or not message.author.voice:
                    await message.reply("Você precisa estar em um Canal de Voz para me chamar!")
                    return
                
                channel = message.author.voice.channel
                try:
                    vc = await channel.connect(timeout=60.0)
                    console.print(f"[bold green]Entrei no canal de voz: {channel.name}[/bold green]")
                    
                    instrucoes = ("**Estou na Call! 🎧🎙️**\n"
                                  "> **Nota Técnica:** Eu não fico ouvindo sua voz viva 24h sem parar na call, pois isso derreteria o custo do projeto!\n\n"
                                  "**Como falar comigo:**\n"
                                  "1. Use o botão de `Mensagem de Voz` original aqui do Chat do Discord (Ícone de microfone ao lado do botão de Emoji).\n"
                                  "2. Grave o seu áudio falando pra mim e mande.\n"
                                  "3. Eu vou baixar o áudio em milissegundos, usar o **Voxtral** para ouvir o que você me pediu, e depois vou **REPRODUZIR a resposta FALANDO VIVO** bem alto aqui no canal de voz para todos escutarem!")
                    await message.reply(instrucoes)
                except Exception as e:
                    console.print(f"[bold red]Erro ao entrar no canal de voz: {e}[/bold red]")
                    await message.reply("Opa, rolou um problema (TimeOut) ao entrar na call.")
                return

            if message.content.lower().startswith('!disconnect'):
                for vc in self.voice_clients:
                    if vc.guild == message.guild:
                        await vc.disconnect()
                        await message.reply("Saí da call!")
                        return
                return
                
            if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
                peer_id = str(message.author.id)
                peer_name = str(message.author)
                
                # Pega o texto da mensagem e remove a marcação de arroba (@MoltyClaw)
                user_text = message.content.replace(f'<@{self.user.id}>', '').strip()
                
                console.print(f"\n[bold magenta]📩 Discord ({message.author}):[/bold magenta] {user_text[:200]}...")
                
                # Transcrição de áudio
                for attachment in message.attachments:
                    if attachment.content_type and ('audio' in attachment.content_type or attachment.filename.endswith('.ogg')):
                        import time
                        from pathlib import Path
                        temp_dir = Path(os.path.join(MOLTY_DIR, "temp"))
                        temp_dir.mkdir(exist_ok=True)
                        file_path = temp_dir / f"discord_audio_{int(time.time())}.ogg"
                        await attachment.save(file_path)
                        
                        console.print(f"[info]🎧 Áudio do Discord detectado, transcrevendo...[/info]")
                        transcribed = hub.transcribe_audio_sync(str(file_path))
                        if transcribed:
                            user_text += f"\n(Áudio Anexado Transcrito do Usuário): '{transcribed}'"
                            console.print(f"[bold yellow]Transcrição:[/] {transcribed}")
                
                if not user_text:
                    return
                
                # Verifica se user e bot estão na mesma call
                in_same_vc = False
                if hasattr(message.author, 'voice') and message.author.voice and message.author.voice.channel:
                    for vc in self.voice_clients:
                        if vc.guild == message.guild and vc.is_connected() and vc.channel == message.author.voice.channel:
                            in_same_vc = True
                            break
                
                if in_same_vc:
                    user_text += f"\n\n[INSTRUÇÃO DE SISTEMA: Você está na mesma sala de voz que o usuário no Discord! USE A TOOL 'VOICE_REPLY' OBRIGATORIAMENTE PARA GERAR A SUA RESPOSTA EM ÁUDIO NESTE TURNO!]"
                
                async def keep_typing():
                    while True:
                        try:
                            async with message.channel.typing():
                                await asyncio.sleep(8)
                        except asyncio.CancelledError:
                            break
                        except Exception:
                            break
                
                typing_task = asyncio.create_task(keep_typing())

                # Exibe as Tools chamadas pelo MoltyClaw no canal (igual à WebUI)
                async def tool_callback(msg: str):
                    try:
                        await message.channel.send(f"⚙️ {msg}")
                    except Exception:
                        pass

                try:
                    reply = await asyncio.wait_for(
                        hub.ask(
                            user_text,
                            channel="discord",
                            peer_id=peer_id,
                            peer_name=peer_name,
                            tool_callback=tool_callback,
                        ),
                        timeout=300.0
                    )
                except asyncio.TimeoutError:
                    await message.channel.send("⏱️ Essa tarefa está demorando! Vou continuar processando em background...")
                    reply = await hub.ask(user_text, channel="discord", peer_id=peer_id, peer_name=peer_name, tool_callback=tool_callback)
                finally:
                    typing_task.cancel()
                    try:
                        await typing_task
                    except asyncio.CancelledError:
                        pass
                
                if not reply or not isinstance(reply, str):
                    await message.channel.send("Mals aí, o cérebro da IA não me deu uma resposta válida! (Cheque as chaves de API).")
                    return
                
                import re
                media_path = None
                audio_reply_path = None
                
                match_img = re.search(r'\[SCREENSHOT_TAKEN:\s*(.*?)\]', reply)
                if match_img:
                    media_path = match_img.group(1).strip()
                    reply = reply.replace(match_img.group(0), "").strip()
                    if not os.path.isabs(media_path) and not os.path.exists(media_path):
                        potential_path = os.path.join(hub.agent.base_dir, "temp", media_path)
                        if os.path.exists(potential_path):
                            media_path = potential_path
                    
                match_aud = re.search(r'\[AUDIO_REPLY:\s*(.*?)\]', reply)
                if match_aud:
                    audio_reply_path = match_aud.group(1).strip()
                    reply = reply.replace(match_aud.group(0), "").strip()
                    if not os.path.isabs(audio_reply_path) and not os.path.exists(audio_reply_path):
                        potential_path = os.path.join(hub.agent.base_dir, "temp", audio_reply_path)
                        if os.path.exists(potential_path):
                            audio_reply_path = potential_path
                    
                if len(reply) > 2000:
                    chunks = [reply[i:i+1900] for i in range(0, len(reply), 1900)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                    if media_path and os.path.exists(media_path):
                        await message.channel.send(file=discord.File(media_path))
                else:
                    if media_path and os.path.exists(media_path):
                        if reply:
                            await message.channel.send(reply, file=discord.File(media_path))
                        else:
                            await message.channel.send(file=discord.File(media_path))
                    elif reply:
                        await message.channel.send(reply)
                    
                    if audio_reply_path and os.path.exists(audio_reply_path):
                        bot_in_voice = False
                        for vc in self.voice_clients:
                            if vc.guild == message.guild and vc.is_connected():
                                bot_in_voice = True
                                if not vc.is_playing():
                                    console.print(f"[info]Falando a resposta no canal de voz...[/info]")
                                    ffmpeg_path = r"C:\Users\Cliente\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"
                                    if not os.path.exists(ffmpeg_path):
                                        ffmpeg_path = "ffmpeg"
                                    vc.play(discord.FFmpegPCMAudio(source=audio_reply_path, executable=ffmpeg_path))
                                else:
                                    await message.channel.send("(Nota: Molty já está falando algo no Voice Chat!)")
                                break
                        
                        if not bot_in_voice:
                            await message.channel.send(file=discord.File(audio_reply_path))
                    
        except asyncio.CancelledError:
            console.print(f"[bold yellow]⚠️ on_message cancelado - ignorando para manter bot ativo[/bold yellow]")
            return
        except Exception as e:
            console.print(f"[bold red]❌ Erro não tratado em on_message: {e}[/bold red]\n{traceback.format_exc()}")
            return

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        console.print("[bold red]❌ ERRO: A variável DISCORD_TOKEN não foi encontrada no seu .env![/bold red]")
        console.print("[yellow]Edite o arquivo .env e adicione seu token igual o exemplo abaixo:[/yellow]")
        console.print("DISCORD_TOKEN=OTExMjUx...")
    else:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        client = MoltyClawDiscordBot(intents=intents, name="MoltyClaw (Discord)")

        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        try:
            client.run(DISCORD_TOKEN)
        except discord.errors.PrivilegedIntentsRequired:
            console.print("\n[bold red]❌ ERRO DE PERMISSÃO (INTENTS) NO DISCORD![/bold red]")
            console.print("[yellow]O seu bot do Discord precisa de permissões especiais ativadas no Developer Portal:[/yellow]")
            console.print("1. Acesse: https://discord.com/developers/applications/")
            console.print("2. Selecione sua aplicação.")
            console.print("3. Vá em 'Bot' no menu lateral.")
            console.print("4. Ative: [bold]MESSAGE CONTENT INTENT[/bold]")
            console.print("5. Ative: [bold]SERVER MEMBERS INTENT[/bold]")
            console.print("6. Salve as mudanças e tente rodar novamente.\n")
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]❌ Erro fatal ao iniciar o bot do Discord: {e}[/bold red]")
            sys.exit(1)
