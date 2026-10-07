async def execute_youtube_action(action: str, param: str) -> str:
    try:
        if action == "YOUTUBE_SUMMARIZE":
            from youtube_transcript_api import YouTubeTranscriptApi

            video_id = None
            if "v=" in param:
                video_id = param.split("v=")[1].split("&")[0]
            elif "youtu.be/" in param:
                video_id = param.split("youtu.be/")[1].split("?")[0]

            if not video_id:
                return "ERRO: O param fornecido não parece ser uma URL válida de vídeo do YouTube, formato suportado: youtube.com/watch?v=XXXX ou youtu.be/XXXX."

            try:
                try:
                    try:
                        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'pt-BR', 'en', 'en-US'])
                    except Exception:
                        transcript = YouTubeTranscriptApi.get_transcript(video_id)
                    full_text = " ".join([t['text'] for t in transcript])
                except AttributeError:
                    api = YouTubeTranscriptApi()
                    try:
                        t = api.fetch(video_id, languages=['pt', 'pt-BR', 'en', 'en-US'])
                    except Exception:
                        t = api.fetch(video_id)
                    full_text = " ".join([snippet.text for snippet in t.snippets])

            except Exception as ex:
                return f"Não foi possível resgatar as legendas pra esse vídeo (talvez as legendas precisem de login ou não existam). Erro interno: {ex}"

            max_chars = 15000
            return f"Transcrição extraída com sucesso. Aqui está o conteúdo falado no vídeo (resuma com base nisso):\n\n{full_text[:max_chars]}"

        return f"Ação YouTube desconhecida: {action}"
    except Exception as e:
        return f"Exceção Módulo YouTube ({action}): {e}"