import os
import asyncio
import traceback
import discord
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moltyclaw import MoltyClaw
import aiohttp
import socket

# Correção para o aiohttp no Windows com Python 3.10+ (Evita travamentos do aiohappyeyeballs e TimeoutError de IPv6)
_orig_tcp_init = aiohttp.TCPConnector.__init__
def _new_tcp_init(self, *args, **kwargs):
    kwargs['family'] = socket.AF_INET
    _orig_tcp_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _new_tcp_init

from rich.console import Console
console = Console()
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class MoltyClawDiscordBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agent = MoltyClaw(name="MoltyClaw (Discord)")

    async def setup_hook(self):
        # Essa função do discord.Client é ideal para inicializar o Browser assíncrono!
        console.print("[bold green]Inicializando navegador do MoltyClaw para o Discord...[/bold green]")
        await self.agent.init_browser()
        console.print("[bold green]Navegador ligado e pronto para pesquisas![/bold green]")

    async def on_ready(self):
        console.print(f"[bold blue]🤖 Conectado no Discord escutando como {self.user}![/bold blue]")
        
        # Tenta renomear o Bot automaticamente na plataforma (Atenção: o Discord bloqueia se tentar muitas vezes)
        try:
            if self.user.name != "MoltyClaw":
                await self.user.edit(username="MoltyClaw")
                console.print("[dim green]>> Nome de usuário do bot alterado para 'MoltyClaw'![/dim green]")
        except Exception as e:
            console.print(f"[dim yellow]>> Aviso: Não foi possível alterar o username sozinho (Rate Limit?): {e}[/dim yellow]")
        
        # Define a descrição/status visual embaixo do nome do bot (Playing / Jogando)
        await self.change_presence(activity=discord.Game(name="Hello, I am MoltyClaw, your best friend 🤖"))
        console.print("[dim green]>> Presença visual do bot atualizada com sucesso![/dim green]")

    async def on_message(self, message):
        # Ignora mensagens enviadas pelo próprio bot (previne loops infinitos)
        if message.author == self.user:
            return
            
        allowed_users = os.getenv("DISCORD_ALLOWED_USERS", "")
        if allowed_users.strip():
            allowed_list = [u.strip() for u in allowed_users.split(",")]
            if str(message.author.id) not in allowed_list:
                console.print(f"[bold yellow][Segurança] Ignorando Discord de não autorizado: {message.author} ({message.author.id})[/bold yellow]")
                return
            
        # O MoltyClaw vai responder se for mencionado numa sala, via Comando CALL, ou se for numa Mensagem Direta (DM) com alguém.
        # Assim ele não fica tentando responder o server de Discord inteiro o tempo todo.
        
        # CHECAGEM DO COMANDO DE ENTRAR E SAIR DA CALL
        if message.content.lower().startswith('!call'):
            if not hasattr(message.author, 'voice') or not message.author.voice:
                await message.reply("Você precisa estar em um Canal de Voz para me chamar!")
                return
            
            channel = message.author.voice.channel
            try:
                # O Discord em algumas redes demora pra bater o Handshake UDP do Voice, aumentando o timeout evita bug de entrar e cair
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
            
            # Pega o texto da mensagem e remove a marcação de arroba (@MoltyClaw)
            user_text = message.content.replace(f'<@{self.user.id}>', '').strip()
            
            # Checa attachments de audio
            for attachment in message.attachments:
                if attachment.content_type and ('audio' in attachment.content_type or attachment.filename.endswith('.ogg')):
                    import time
                    from pathlib import Path
                    temp_dir = Path("temp")
                    temp_dir.mkdir(exist_ok=True)
                    file_path = temp_dir / f"discord_audio_{int(time.time())}.ogg"
                    await attachment.save(file_path)
                    
                    console.print("[info]🎧 Áudio do Discord detectado, transcrevendo...[/info]")
                    transcribed = await self.agent.transcribe_audio(str(file_path))
                    if transcribed:
                        user_text += f"\n(Áudio Anexado Transcrito do Usuário): '{transcribed}'"
                        console.print(f"[bold yellow]Transcrição:[/] {transcribed}")
            
            if not user_text:
                return
            
            # Verifica se user e bot estao na mesma call, se sim, OBRIGA a tool de voz
            in_same_vc = False
            if hasattr(message.author, 'voice') and message.author.voice and message.author.voice.channel:
                for vc in self.voice_clients:
                    if vc.guild == message.guild and vc.is_connected() and vc.channel == message.author.voice.channel:
                        in_same_vc = True
                        break
            
            if in_same_vc:
                user_text += "\n\n[INSTRUÇÃO DE SISTEMA: Você está na mesma sala de voz que o usuário no Discord! Seu áudio será roteado ativamente pra ele escutar! MUDANÇA DE ROTINA: USE A TOOL 'VOICE_REPLY' OBRIGATORIAMENTE PARA GERAR A SUA RESPOSTA EM ÁUDIO NESTE TURNO, DO CONTRÁRIO ELE SÓ VERÁ TEXTO CALADO E ACHARÁ QUE VOCÊ QUEBROU!]"

            console.print(f"\n[bold magenta]📩 Mensagem Discord ({message.author}):[/bold magenta] {user_text[:200]}...")
            
            # Coloca a interface do Discord mostrando o indicativo "MoltyClaw está digitando..."
            async with message.channel.typing():
                try:
                    # Chama o motor inteligência artificial que consome ferramentas
                    reply = await self.agent.ask(user_text)
                    
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
                        
                    # O Discord tem um limite de 2000 caracteres pra mensagem
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
                            
                        # Manda o áudio narrado se existir
                        if audio_reply_path and os.path.exists(audio_reply_path):
                            # Teta achar se o bot está numa de voz para tocar direto, se não estiver, joga como Anexo no chat
                            bot_in_voice = False
                            for vc in self.voice_clients:
                                if vc.guild == message.guild and vc.is_connected():
                                    bot_in_voice = True
                                    if not vc.is_playing():
                                        console.print(f"[info]Falando a resposta no canal de voz...[/info]")
                                        # Corrige o caminho absoluto se ffpmeg nao estiver no PATH nativo da instancia Python
                                        ffmpeg_path = r"C:\Users\Cliente\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin\ffmpeg.exe"
                                        if not os.path.exists(ffmpeg_path):
                                            ffmpeg_path = "ffmpeg"
                                        vc.play(discord.FFmpegPCMAudio(source=audio_reply_path, executable=ffmpeg_path))
                                    else:
                                        await message.channel.send("(Nota: Molty já está falando algo no Voice Chat!)")
                                    break
                            
                            if not bot_in_voice:
                                await message.channel.send(file=discord.File(audio_reply_path))
                        
                        
                except Exception as e:
                    console.print(f"\n[bold red]Erro processando chat do Discord: {e}[/bold red]\n{traceback.format_exc()}")
                    await message.channel.send("Mals aí, fundi um pino aqui tentando processar sua mensagem! 🤖💥")

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        console.print("[bold red]❌ ERRO: A variável DISCORD_TOKEN não foi encontrada no seu .env![/bold red]")
        console.print("[yellow]Edite o arquivo .env e adicione seu token igual o exemplo abaixo:[/yellow]")
        console.print("DISCORD_TOKEN=OTExMjUx...")
    else:
        # Pede permissão explícita pro Discord para ler conteúdo das mensagens em servidores!
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True # Pra saber quem ta em call
        
        client = MoltyClawDiscordBot(intents=intents)
        
        # Seta o loop do windows pra evitar bug de subprocess assíncrono
        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        client.run(DISCORD_TOKEN)
