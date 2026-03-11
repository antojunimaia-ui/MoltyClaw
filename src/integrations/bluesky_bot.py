import os
import asyncio
import traceback
import time
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from moltyclaw import MoltyClaw
from rich.console import Console

console = Console()
load_dotenv()

BLUESKY_HANDLE   = os.getenv("BLUESKY_HANDLE", "").lstrip("@")    # ex: seunome.bsky.social
BLUESKY_PASSWORD = os.getenv("BLUESKY_APP_PASSWORD")  # App Password (não a senha principal)

# Intervalo de polling (segundos). Bluesky não tem rate limits super rígidos,
# mas 15s é suficiente para reatividade sem abusar.
POLL_INTERVAL = 15


async def send_bluesky_reply(client, text: str, root_ref, parent_ref):
    """Posta um reply em thread no Bluesky, respeitando limite de 300 chars."""
    if len(text) > 300:
        text = text[:297] + "..."
    
    from atproto import models
    client.send_post(
        text=text,
        reply_to=models.AppBskyFeedPost.ReplyRef(
            root=root_ref,
            parent=parent_ref,
        )
    )


async def main_loop():
    if not BLUESKY_HANDLE or not BLUESKY_PASSWORD:
        console.print("[bold red]❌ ERRO: Faltam credenciais do Bluesky no .env![/bold red]")
        console.print("[yellow]Adicione:[/yellow]")
        console.print("  BLUESKY_HANDLE=seunome.bsky.social")
        console.print("  BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx")
        return

    # Importa atproto aqui para dar erro amigável se não estiver instalado
    try:
        from atproto import Client
    except ImportError:
        console.print("[bold red]❌ ERRO: Biblioteca 'atproto' não instalada![/bold red]")
        console.print("[yellow]Rode: pip install atproto[/yellow]")
        return

    console.print("[bold green]Inicializando navegador do MoltyClaw para o Bluesky...[/bold green]")
    agent = MoltyClaw(name="MoltyClaw (Bluesky)")
    await agent.init_browser()
    if agent.mcp_hub:
        await agent.mcp_hub.connect_servers()
    console.print("[bold green]Navegador e conectores MCP prontos![/bold green]")

    # Autenticar no Bluesky com App Password
    # O Client do atproto é síncrono. Chamamos em thread para não bloquear o loop.
    client = Client()
    try:
        profile = await asyncio.get_event_loop().run_in_executor(
            None, lambda: client.login(BLUESKY_HANDLE, BLUESKY_PASSWORD)
        )
        my_did = profile.did
        my_handle = profile.handle
        console.print(f"[bold blue]🦋 Conectado no Bluesky como @{my_handle} (DID: {my_did})[/bold blue]")
    except Exception as e:
        console.print(f"[bold red]❌ Falha ao autenticar no Bluesky: {e}[/bold red]")
        if agent.mcp_hub:
            await agent.mcp_hub.cleanup()
        await agent.close_browser()
        return

    # Pega uma whitelist opcional de handles permitidos
    allowed_raw = os.getenv("BLUESKY_ALLOWED_HANDLES", "")
    allowed_handles = [h.strip().lstrip("@") for h in allowed_raw.split(",") if h.strip()]

    # Rastreia notificações já processadas por seenAt timestamp
    last_seen_at = None

    try:
        while True:
            try:
                # Busca notificações não lidas (replies, mentions, quotes)
                resp = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: client.app.bsky.notification.list_notifications({"limit": 15})
                )

                notifications = resp.notifications if resp.notifications else []

                new_notifications = []
                for notif in notifications:
                    # Filtra apenas menções e replies ao bot
                    if notif.reason not in ("mention", "reply"):
                        continue

                    # Evita reprocessar notificações antigas pela indexedAt timestamp
                    if last_seen_at and notif.indexed_at <= last_seen_at:
                        continue

                    # Não responde ao próprio bot
                    if notif.author.did == my_did:
                        continue

                    new_notifications.append(notif)

                # Marca todas como lidas no servidor após coletar
                if new_notifications:
                    await asyncio.get_event_loop().run_in_executor(
                        None, lambda: client.app.bsky.notification.update_seen(
                            {"seen_at": notifications[0].indexed_at}
                        )
                    )
                    last_seen_at = notifications[0].indexed_at

                # Processa do mais antigo ao mais novo
                for notif in reversed(new_notifications):
                    author_handle = notif.author.handle

                    # Whitelist
                    if allowed_handles and author_handle not in allowed_handles:
                        console.print(f"[bold yellow][Segurança] Ignorando Bluesky de não autorizado: @{author_handle}[/bold yellow]")
                        continue

                    # Extrai o texto da notificação
                    record = notif.record
                    user_text = getattr(record, "text", "") or ""
                    # Remove a menção do próprio handle se presente
                    user_text = user_text.replace(f"@{my_handle}", "").strip()

                    if not user_text:
                        continue

                    console.print(f"\n[bold magenta]📩 Bluesky (@{author_handle}):[/bold magenta] {user_text[:200]}")

                    try:
                        reply_text = await agent.ask(user_text)

                        # Limpa marcadores internos de screenshot/audio
                        import re
                        reply_text = re.sub(r'\[SCREENSHOT_TAKEN:\s*(.*?)\]', '', reply_text).strip()
                        reply_text = re.sub(r'\[AUDIO_REPLY:\s*(.*?)\]', '', reply_text).strip()

                        # Bluesky suporta até 300 caracteres por post
                        if len(reply_text) > 300:
                            reply_text = reply_text[:297] + "..."

                        # Monta referências para o reply em thread
                        from atproto import models
                        post_uri = notif.uri
                        post_cid = notif.cid

                        # root_ref: se for reply, usa o root original; se for mention, é o próprio post
                        if notif.reason == "reply" and hasattr(record, "reply") and record.reply:
                            root_ref = models.ComAtprotoRepoStrongRef.Main(
                                uri=record.reply.root.uri,
                                cid=record.reply.root.cid,
                            )
                        else:
                            root_ref = models.ComAtprotoRepoStrongRef.Main(
                                uri=post_uri,
                                cid=post_cid,
                            )

                        parent_ref = models.ComAtprotoRepoStrongRef.Main(
                            uri=post_uri,
                            cid=post_cid,
                        )

                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: client.send_post(
                                text=reply_text,
                                reply_to=models.AppBskyFeedPost.ReplyRef(
                                    root=root_ref,
                                    parent=parent_ref,
                                )
                            )
                        )

                        console.print(f"[dim green]>> Resposta enviada no Bluesky para @{author_handle}.[/dim green]")

                    except Exception as inner_e:
                        console.print(f"[bold red]Erro ao processar IA ou postar no Bluesky: {inner_e}[/bold red]\n{traceback.format_exc()}")

            except Exception as e:
                console.print(f"[dim yellow]Erro checando notificações no Bluesky: {e}[/dim yellow]")

            await asyncio.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        console.print("[bold yellow]Desligando navegador do Bluesky...[/bold yellow]")
        await agent.close_browser()


if __name__ == "__main__":
    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main_loop())
