import os
import asyncio
import traceback
import tweepy
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moltyclaw import MoltyClaw
from rich.console import Console

console = Console()
load_dotenv()

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

# Tempo em segundos entre as checagens (API Gratuita tem limites rigorosos)
POLL_INTERVAL = 30

async def main_loop():
    if not all([BEARER_TOKEN, API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        console.print("[bold red]❌ ERRO: Faltam tokens do Twitter no arquivo .env![/bold red]")
        console.print("[yellow]Certifique-se de configurar: TWITTER_BEARER_TOKEN, TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN e TWITTER_ACCESS_TOKEN_SECRET[/yellow]")
        return
        
    console.print("[bold green]Inicializando navegador do MoltyClaw para o Twitter...[/bold green]")
    agent = MoltyClaw(name="MoltyClaw (Twitter)")
    await agent.init_browser()
    console.print("[bold green]Navegador ligado e pronto para pesquisas![/bold green]")
    
    # Criar cliente API v2 do Twitter
    client = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=API_KEY,
        consumer_secret=API_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
        wait_on_rate_limit=True
    )
    
    try:
        me = client.get_me()
        my_id = me.data.id
        my_username = me.data.username
        console.print(f"[bold blue]🐦 Conectado no X (Twitter) como @{my_username}![/bold blue]")
    except Exception as e:
        console.print(f"[bold red]❌ Falha ao autenticar no X: {e}[/bold red]")
        return

    last_tweet_id = None

    try:
        while True:
            try:
                # Buscar menções recentes
                response = client.get_users_mentions(id=my_id, since_id=last_tweet_id, max_results=5, tweet_fields=["author_id", "created_at"])
                
                if response.data:
                    # Inverter para responder as mais antigas primeiro
                    for tweet in reversed(response.data):
                        # Pular se o próprio bot gerou (loop infinito)
                        if tweet.author_id == my_id:
                            continue
                            
                        last_tweet_id = tweet.id
                        user_text = tweet.text.replace(f"@{my_username}", "").strip()
                        
                        console.print(f"\n[bold magenta]📩 Menção X/Twitter (Tweet ID: {tweet.id}):[/bold magenta] {user_text}")
                        
                        try:
                            reply = await agent.ask(user_text)
                            
                            # X/Twitter tem limite de 280 chars no free / padrao
                            # Além disso, extrair screenshot não sendo possivel nativamente via upload de media na v2 free (precisa da v1)
                            # Mas podemos enviar a resposta.
                            
                            # Limpeza de screenshots do output pra não poluir.
                            import re
                            reply = re.sub(r'\[SCREENSHOT_TAKEN:\s*(.*?)\]', '', reply).strip()

                            if len(reply) > 280:
                                reply = reply[:277] + "..."

                            client.create_tweet(text=reply, in_reply_to_tweet_id=tweet.id)
                            console.print(f"[dim green]>> Resposta enviada com sucesso no X.[/dim green]")
                            
                        except Exception as inner_e:
                            console.print(f"[bold red]Erro processando a IA ou postando no X: {inner_e}[/bold red]\n{traceback.format_exc()}")
                            
            except Exception as e:
                console.print(f"[dim yellow]Erro checando menções no X (Rate Limit?): {e}[/dim yellow]")
            
            await asyncio.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        pass
    finally:
        console.print("[bold yellow]Desligando navegador do Twitter...[/bold yellow]")
        await agent.close_browser()

if __name__ == "__main__":
    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
    asyncio.run(main_loop())
