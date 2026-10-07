import os
import asyncio

async def execute_spotify_action(action: str, param: str) -> str:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080")

    if not client_id or not client_secret:
        return "ERRO: Ferramentas do Spotify exigem as chaves SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no .env."

    def _run_spotify_sync():
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        scope = "user-read-playback-state,user-modify-playback-state"
        sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope
            ),
            requests_timeout=15
        )

        devices = sp.devices()
        if not devices or not devices['devices']:
            return "ERRO: Nenhum dispositivo tocando ou online no Spotify agora. Peça para o usuário abrir o App primeiro!"

        if action == "SPOTIFY_SEARCH":
            results = sp.search(q=param, limit=5, type='track')
            if not results['tracks']['items']:
                return "Nenhuma música encontrada com esse nome."
            res_txt = ""
            for idx, track in enumerate(results['tracks']['items']):
                res_txt += f"{idx+1}. {track['name']} - {track['artists'][0]['name']} (URI: {track['uri']})\n"
            return "Resultado da Busca:\n" + res_txt

        elif action == "SPOTIFY_PLAY":
            if "spotify:track:" in param:
                sp.start_playback(uris=[param])
                return f"Música com URI '{param}' começou a tocar!"
            else:
                results = sp.search(q=param, limit=1, type='track')
                if not results['tracks']['items']:
                    return "Não encontrei essa música para tocar."
                tkt = results['tracks']['items'][0]
                sp.start_playback(uris=[tkt['uri']])
                return f"Tocando agora: {tkt['name']} by {tkt['artists'][0]['name']}!"

        elif action == "SPOTIFY_PAUSE":
            sp.pause_playback()
            return "Playback pausado."

        elif action == "SPOTIFY_ADD_QUEUE":
            sp.add_to_queue(param)
            return f"Adicionado à fila de reprodução: {param}."

        return "Ação desconhecida."

    try:
        return await asyncio.wait_for(asyncio.to_thread(_run_spotify_sync), timeout=20.0)
    except asyncio.TimeoutError:
        return "ERRO_TIMEOUT: A API do Spotify demorou muito para responder (mais de 20 segundos) e a requisição foi cancelada automaticamente!"
    except Exception as e:
        return f"Erro Módulo Spotify ({action}): {e}"