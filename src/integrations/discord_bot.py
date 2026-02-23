import os
import asyncio
import traceback
import discord
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moltyclaw import MoltyClaw
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
            
        # O MoltyClaw vai responder se for mencionado numa sala ou se for numa Mensagem Direta (DM) com alguém.
        # Assim ele não fica tentando responder o server de Discord inteiro o tempo todo.
        if isinstance(message.channel, discord.DMChannel) or self.user in message.mentions:
            
            # Pega o texto da mensagem e remove a marcação de arroba (@MoltyClaw)
            user_text = message.content.replace(f'<@{self.user.id}>', '').strip()
            
            console.print(f"\n[bold magenta]📩 Mensagem Discord ({message.author}):[/bold magenta] {user_text}")
            
            # Coloca a interface do Discord mostrando o indicativo "MoltyClaw está digitando..."
            async with message.channel.typing():
                try:
                    # Chama o motor inteligência artificial que consome ferramentas
                    reply = await self.agent.ask(user_text)
                    
                    import re
                    media_path = None
                    match = re.search(r'\[SCREENSHOT_TAKEN:\s*(.*?)\]', reply)
                    if match:
                        media_path = match.group(1)
                        reply = reply.replace(match.group(0), "").strip()
                        
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
        
        client = MoltyClawDiscordBot(intents=intents)
        
        # Seta o loop do windows pra evitar bug de subprocess assíncrono
        if os.name == 'nt':
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
        client.run(DISCORD_TOKEN)
