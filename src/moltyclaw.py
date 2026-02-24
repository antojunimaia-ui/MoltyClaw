import os
import asyncio
import traceback
import re
from playwright.async_api import async_playwright
from dotenv import load_dotenv

from mistralai.async_client import MistralAsyncClient
from mistralai.models.chat_completion import ChatMessage

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.theme import Theme

load_dotenv()

custom_theme = Theme({
    "info": "dim cyan",
    "warning": "magenta",
    "error": "bold red",
    "moltyclaw": "bold green",
    "user": "bold blue"
})
console = Console(theme=custom_theme)

class MoltyClaw:
    def __init__(self, name="MoltyClaw"):
        self.name = name
        self.api_key = os.getenv("MISTRAL_API_KEY")
        
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
        active_features = []
        if os.environ.get("MOLTY_WHATSAPP_ACTIVE"):
            active_features.append('"WHATSAPP_SEND" (param: "numero | opcional texto | opcional caminho arquivo absoluto")')
        if os.environ.get("MOLTY_DISCORD_ACTIVE"):
            active_features.append('"DISCORD_SEND" (param: "id_usuario_ou_chat | opcional texto | opcional caminho arquivo absoluto")')
        if os.environ.get("MOLTY_TELEGRAM_ACTIVE"):
            active_features.append('"TELEGRAM_SEND" (param: "id_ou_username | opcional texto | opcional caminho arquivo absoluto")')
        if os.environ.get("MOLTY_TWITTER_ACTIVE"):
            active_features.append('"X_POST" (param: "texto do tweet de ate 280 chars")')
        
        active_features.append('"VOICE_REPLY" (param: "texto curto de reposta em voz | numero zap_ID discord_ou_ID telegram SE voce quiser enviar ativamente para alguem em vez de só responder o chat atual")')

        self.history = [
            ChatMessage(
                role="system",
                content=f"""Você é o {self.name}, um agente autônomo com um NAVEGADOR COMPLETO ao seu dispor.
Você PODE usar a internet e o terminal para obter informações ou interagir com sites (clicar, digitar, extrair dados).

REGRA DE OURO PARA BATE-PAPO: Se o usuário apenas disser "olá", "tudo bem" ou fizer uma pergunta cujo conhecimento você já possui na sua cabeça, responda NORMALMENTE e diretamente em texto, SEM USAR O BLOCO <tool>! 

REGRA PARA AÇÕES REAIS: Se o usuário pedir para buscar algo na internet, abrir um site real, ou interagir com o terminal/sistema do usuário, ENTÃO você DEVE gerar um bloco JSON da ferramenta.

Para executar uma ação, responda EXATAMENTE nesse formato JSON (você deve usar o bloco <tool>):

<tool>
{{"action": "GOTO", "param": "https://site.com"}}
</tool>

Ações suportadas no JSON:
"GOTO" (param: url)
"CLICK" (param: seletor css)
"TYPE" (param: "seletor | texto")
"READ_PAGE" (param: "")
"INSPECT_PAGE" (param: "")
"SCREENSHOT" (param: "")
"CMD" (param: comando de terminal)
"DDG_SEARCH" (param: "sua busca no duckduckgo sem precisar usar browser")
"READ_EMAILS" (param: limite)
"SEND_EMAIL" (param: destinatario | assunto | corpo)
"DELETE_EMAIL" (param: id_do_email)
"MEMORY_SAVE_LONG_TERM" (param: "conteúdo a salvar no MEMORY.md")
"MEMORY_SAVE_DAILY" (param: "ocorrência pra o diário de curto prazo")
"MEMORY_SEARCH" (param: "sua busca. ex: projeto, compilar")
"MEMORY_GET" (param: "caminho do arquivo md")
"SPOTIFY_PLAY" (param: nome da música ou URI)
"SPOTIFY_PAUSE" (param: "")
"SPOTIFY_SEARCH" (param: nome do artista ou música)
"SPOTIFY_ADD_QUEUE" (param: URI da música)
"YOUTUBE_SUMMARIZE" (param: link_do_video)
{chr(10).join(active_features)}

IMPORTANTE: Você só pode usar UMA ferramenta por vez. O retorno de busca de memória te dirá os arquivos, use MEMORY_GET para lê-los. Se desejar ficar quieto num turno de background, diga apenas NO_REPLY no texto da resposta."""
            )
        ]
        
        if not self.api_key:
            console.print(f"[{self.name}] [warning]Aviso: MISTRAL_API_KEY não encontrada.[/warning]")
            self.mistral_client = None
        else:
            self.mistral_client = MistralAsyncClient(api_key=self.api_key)

    async def init_browser(self):
        """Inicializa o navegador persistente."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                channel="msedge",
                ignore_default_args=["--enable-automation"],
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--window-position=0,0'
                ]
            )
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
                viewport={"width": 1366, "height": 768},
                device_scale_factor=1,
                has_touch=False,
                is_mobile=False,
                locale='pt-BR',
                timezone_id='America/Sao_Paulo',
                color_scheme='dark'
            )
            
            # Força a remoção profunda da assinatura webdriver do JS
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            self.page = await self.context.new_page()
            
            # Applica o stealth pro google maldito não bugar a pesquisa com Captcha
            try:
                from playwright_stealth import Stealth
                await Stealth().apply_stealth_async(self.context)
                console.print(f"[info][{self.name}] 🥷 Stealth Anti-Bot Mode Ativado no Browser![/info]")
            except ImportError as e:
                console.print(f"[warning][{self.name}] playwright-stealth ausente ou com problema ({e}). O navegador operará em modo normal (suscetível a Captcha).[/warning]")
                
            console.print(f"[info][{self.name}] Navegador interno persistente inicializado![/info]")
        except Exception as e:
            console.print(f"[error]Erro ao iniciar navegador: {e}[/error]")

    async def close_browser(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def execute_terminal_command(self, command: str) -> str:
        console.print(f"[info][{self.name}] Executando comando:[/info] {command}")
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()
            if process.returncode != 0:
                return f"Erro (código {process.returncode}):\n{error}"
            return output if output else "Comando executado com sucesso."
        except Exception as e:
            return f"Exceção: {e}"

    async def run_browser_action(self, action: str, param: str) -> str:
        if not self.page:
            return "Erro: Navegador não inicializado."
            
        try:
            if action == "GOTO":
                await self.page.goto(param, timeout=30000)
                await self.page.wait_for_load_state('domcontentloaded')
                title = await self.page.title()
                return f"Página carregada com sucesso. Título da Guia: {title}"
                
            elif action == "CLICK":
                await self.page.click(param, timeout=10000)
                await self.page.wait_for_timeout(2000)  # Aguarda animações ou reações do clique
                return f"Clique efetuado com sucesso no elemento: {param}"
                
            elif action == "TYPE":
                parts = param.split("|", 1)
                if len(parts) != 2:
                    return "Erro: Formato inválido para TYPE. Use [TYPE: seletor | texto]"
                selector = parts[0].strip()
                text = parts[1].strip()
                await self.page.fill(selector, text, timeout=10000)
                return f"Texto '{text}' digitado com sucesso no alvo '{selector}'"
                
            elif action == "READ_PAGE":
                # Avalia o innerText do body inteiro e pega algo cru e facil da IA ler
                content = await self.page.evaluate("document.body.innerText")
                return f"CONTEÚDO TEXTUAL DA PÁGINA ATUAL (truncado): {content[:4000]}"
                
            elif action == "INSPECT_PAGE":
                js_code = """() => {
                    const elements = document.querySelectorAll('a, button, input');
                    let result = [];
                    elements.forEach(el => {
                        let text = (el.innerText || el.value || el.placeholder || el.name || '').replace(/\\n/g, ' ').trim();
                        text = text.substring(0, 50);
                        if (!text && el.tagName.toLowerCase() !== 'input') return;
                        
                        let selector = el.tagName.toLowerCase();
                        if (el.id) selector += '#' + el.id;
                        if (el.className && typeof el.className === 'string') {
                            const classes = el.className.split(' ').filter(c => c).join('.');
                            if (classes) selector += '.' + classes;
                        }
                        
                        if (result.length < 80) {
                            result.push(`[${selector}] -> ${text || 'input/vazio'}`);
                        }
                    });
                    return result.join('\\n');
                }"""
                content = await self.page.evaluate(js_code)
                return f"ELEMENTOS INTERATIVOS DA PÁGINA (máx 80):\n{content}"
                
            elif action == "SCREENSHOT":
                import os
                import time
                path_str = f"screenshot_{int(time.time())}.png"
                await self.page.screenshot(path=path_str, full_page=False)
                return f"Screenshot capturado com sucesso. Se o usuário pediu a imagem, você DEVE dizer essa exata frase no meio do seu texto de volta para ele: [SCREENSHOT_TAKEN: {path_str}]"
                
        except Exception as e:
            return f"Erro durante a execução da ferramenta '{action}': {e}"
                
    async def run_memory_action(self, action: str, param: str) -> str:
        import datetime
        import glob
        
        mem_dir = "memory"
        if not os.path.exists(mem_dir):
            os.makedirs(mem_dir)
            
        today_md = os.path.join(mem_dir, datetime.datetime.now().strftime("%Y-%m-%d") + ".md")
        long_term_md = "MEMORY.md"

        try:
            if action == "MEMORY_SAVE_LONG_TERM":
                with open(long_term_md, "a", encoding="utf-8") as f:
                    f.write(f"\n- {param}\n")
                return f"✅ Salvo permanentemente no {long_term_md}!"
                
            elif action == "MEMORY_SAVE_DAILY":
                with open(today_md, "a", encoding="utf-8") as f:
                    agora = datetime.datetime.now().strftime("%H:%M:%S")
                    f.write(f"[{agora}] {param}\n")
                return f"✅ Salvo no diário {today_md}!"
                
            elif action == "MEMORY_SEARCH":
                query = param.lower()
                results = []
                check_files = [long_term_md] + glob.glob(f"{mem_dir}/*.md")
                
                for fpath in check_files:
                    if os.path.exists(fpath):
                        with open(fpath, "r", encoding="utf-8") as file:
                            for idx, line in enumerate(file):
                                if query in line.lower():
                                    results.append(f"[{fpath} ln:{idx}] {line.strip()[:100]}...")
                if results:
                    return "Encontrado em:\n" + "\n".join(results[:15]) + "\n\nUse MEMORY_GET com o nome do arquivo para ler mais detalhes."
                return "Nenhuma memória semântica encontrada com esse texto."
                
            elif action == "MEMORY_GET":
                if not os.path.exists(param):
                    return "Arquivo não encontrado."
                with open(param, "r", encoding="utf-8") as f:
                    return f.read()[:3000] # Limite para não estourar prompt
                    
        except Exception as e:
            return f"Erro Módulo de Memória: {e}"

    async def execute_gmail_action(self, action: str, param: str) -> str:
        user = os.getenv("GMAIL_USER")
        password = os.getenv("GMAIL_APP_PASSWORD")
        if not user or not password:
            return "ERRO: Ferramenta do Gmail tentou ser usada, mas GMAIL_USER ou GMAIL_APP_PASSWORD não estão configurados no seu .env."
        
        try:
            if action == "READ_EMAILS":
                from imap_tools import MailBox, A
                limit = int(param) if param and param.isdigit() else 5
                result = ""
                with MailBox('imap.gmail.com').login(user, password) as mailbox:
                    for msg in mailbox.fetch(A(all=True), limit=limit, reverse=True):
                        body_txt = msg.text[:400].replace('\\n', ' ')
                        result += f"ID: {msg.uid} | De: {msg.from_} | Assunto: {msg.subject}\nCorpo: {body_txt}...\n\n"
                return result if result else "Caixa de entrada vazia ou erro ao carregar."
                
            elif action == "SEND_EMAIL":
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                parts = param.split('|', 2)
                if len(parts) != 3:
                    return "ERRO: O param deve ser exato no formato 'destinatario | assunto | corpo'"
                to_email, subject, body = [p.strip() for p in parts]
                
                msg = MIMEMultipart()
                msg['From'] = user
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))
                
                # Desativa log de ssl momentaneamente
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
                server.quit()
                return f"E-mail enviado com sucesso para {to_email}!"
                
            elif action == "DELETE_EMAIL":
                from imap_tools import MailBox
                uid = param.strip()
                with MailBox('imap.gmail.com').login(user, password) as mailbox:
                    mailbox.delete(uid)
                return f"E-mail referenciado pelo ID {uid} deletado com sucesso e jogado na Lixeira!"
                
        except Exception as e:
            return f"Exceção Módulo Gmail ({action}): {e}"

    async def execute_spotify_action(self, action: str, param: str) -> str:
        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080")
        
        if not client_id or not client_secret:
            return "ERRO: Ferramentas do Spotify exigem as chaves SPOTIFY_CLIENT_ID e SPOTIFY_CLIENT_SECRET no .env."
            
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            
            # Necessário para controlar reprodução do player do usuário
            scope = "user-read-playback-state,user-modify-playback-state"
            sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                                           client_secret=client_secret,
                                                           redirect_uri=redirect_uri,
                                                           scope=scope))
            
            # Testa se tem algum dispositivo ativo (senão o Playback quebra)
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
                    # Toca um URI específico
                    sp.start_playback(uris=[param])
                    return f"Música com URI '{param}' começou a tocar!"
                else:
                    # Se mandou string pura, busca na hora a primeira track
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
                
        except Exception as e:
            return f"Erro Módulo Spotify ({action}): {e}"

    async def execute_social_send(self, action: str, param: str) -> str:
        if action == "X_POST":
            text = param.strip()
            if len(text) > 280:
                text = text[:277] + "..."
            
            import os
            import tweepy
            try:
                client = tweepy.Client(
                    bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
                    consumer_key=os.getenv("TWITTER_API_KEY"),
                    consumer_secret=os.getenv("TWITTER_API_SECRET"),
                    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
                    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
                )
                # Twitter I/O is blocked if keys are missing
                if not os.getenv("TWITTER_API_KEY"):
                    return "Erro: Token de Twitter ausente."
                
                client.create_tweet(text=text)
                return "Tweet disparado ativamente com sucesso na timeline do X!"
            except Exception as ex:
                return f"Erro na API do Twitter (X) v2: {ex}"

        parts = param.split("|")
        target = parts[0].strip()
        text = parts[1].strip() if len(parts) > 1 else ""
        file_path = parts[2].strip() if len(parts) > 2 else ""
        
        if not text and not file_path:
            return "Erro: Formato inválido. Use [destination | text opcional | file_path opcional]. Providencie pelo menos text ou file."
        
        try:
            import aiohttp
            if action == "TELEGRAM_SEND":
                import os
                token = os.getenv("TELEGRAM_TOKEN")
                if not token: return "Erro: TELEGRAM_TOKEN ausente."
                async with aiohttp.ClientSession() as session:
                    if file_path and os.path.exists(file_path):
                        ext = file_path.lower().split(".")[-1]
                        if ext in ["mp3", "ogg", "wav"]:
                            url = f"https://api.telegram.org/bot{token}/sendVoice"
                            file_field = "voice"
                        elif ext in ["png", "jpg", "jpeg", "webp"]:
                            url = f"https://api.telegram.org/bot{token}/sendPhoto"
                            file_field = "photo"
                        else:
                            url = f"https://api.telegram.org/bot{token}/sendDocument"
                            file_field = "document"
                            
                        form = aiohttp.FormData()
                        form.add_field("chat_id", target)
                        if text: form.add_field("caption", text)
                        form.add_field(file_field, open(file_path, "rb"), filename=os.path.basename(file_path))
                        
                        async with session.post(url, data=form) as resp:
                            if resp.status == 200: return f"Arquivo/Mensagem enviada com sucesso no Telegram para {target}."
                            return f"Erro do Telegram API (HTTP {resp.status}): {await resp.text()}"
                    else:
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        async with session.post(url, json={"chat_id": target, "text": text}) as resp:
                            if resp.status == 200: return f"Mensagem enviada com sucesso no Telegram para {target}."
                            return f"Erro do Telegram API (HTTP {resp.status}): {await resp.text()}"
                        
            elif action == "DISCORD_SEND":
                import os, json
                token = os.getenv("DISCORD_TOKEN")
                if not token: return "Erro: DISCORD_TOKEN ausente."
                url_dm = "https://discord.com/api/v10/users/@me/channels"
                headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
                async with aiohttp.ClientSession() as session:
                    # Tenta abrir DM
                    async with session.post(url_dm, headers=headers, json={"recipient_id": target}) as resp_dm:
                        if resp_dm.status != 200: return f"Erro abrindo DM Discord: {await resp_dm.text()}"
                        dm_data = await resp_dm.json()
                        channel_id = dm_data["id"]
                        url_msg = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                        
                        if file_path and os.path.exists(file_path):
                            form = aiohttp.FormData()
                            payload = {}
                            if text: payload["content"] = text
                            form.add_field("payload_json", json.dumps(payload), content_type="application/json")
                            form.add_field("files[0]", open(file_path, "rb"), filename=os.path.basename(file_path))
                            
                            headers_file = {"Authorization": f"Bot {token}"}
                            
                            async with session.post(url_msg, headers=headers_file, data=form) as resp_msg:
                                if resp_msg.status == 200: return f"Arquivo/Mensagem enviada no Discord com sucesso."
                                return f"Erro Discord (HTTP {resp_msg.status}): {await resp_msg.text()}"
                        else:
                            async with session.post(url_msg, headers=headers, json={"content": text}) as resp_msg:
                                if resp_msg.status == 200: return f"Mensagem enviada no Discord com sucesso."
                                return f"Erro Discord (HTTP {resp_msg.status}): {await resp_msg.text()}"
                            
            elif action == "WHATSAPP_SEND":
                async with aiohttp.ClientSession() as session:
                    if not target.endswith("@c.us"):
                        target = target.replace("+", "").replace("-", "").replace(" ", "") + "@c.us"
                        
                    payload = {"to": target, "message": text}
                    if file_path and os.path.exists(file_path):
                        payload["mediaPath"] = os.path.abspath(file_path)
                        
                    async with session.post("http://localhost:8081/send_whatsapp", json=payload) as resp:
                        if resp.status == 200: return "Mensagem engatilhada e enviada via WhatsApp Bridge Node."
                        return f"O Bridge do WhatsApp reportou erro ou nao esta rodando na porta 8081. (HTTP {resp.status})"
                        
        except Exception as e:
            return f"Exceção interna no módulo Social: {e}"

    async def execute_youtube_action(self, action: str, param: str) -> str:
        try:
            if action == "YOUTUBE_SUMMARIZE":
                from youtube_transcript_api import YouTubeTranscriptApi
                
                # Extrai o ID do vídeo da URL completa
                video_id = None
                if "v=" in param:
                    video_id = param.split("v=")[1].split("&")[0]
                elif "youtu.be/" in param:
                    video_id = param.split("youtu.be/")[1].split("?")[0]
                    
                if not video_id:
                    return "ERRO: O param fornecido não parece ser uma URL válida de vídeo do YouTube, formato suportado: youtube.com/watch?v=XXXX ou youtu.be/XXXX."
                
                try:
                    # Tenta baixar a legenda em português primeiro, senão vai pro inglês
                    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['pt', 'en'])
                except Exception as ex:
                    return f"Não foi possível resgatar as legendas pra esse vídeo (talvez as legendas não existam). Erro interno: {ex}"
                
                # Junta todo o texto da legenda
                full_text = " ".join([t['text'] for t in transcript])
                
                # O Mistral vai truncar naturalmente, mas vamos manter o limite seguro de caracteres passados na ferramenta
                max_chars = 15000 
                return f"Transcrição extraída com sucesso. Aqui está o conteúdo falado no vídeo (resuma com base nisso):\n\n{full_text[:max_chars]}"
                
        except Exception as e:
            return f"Exceção Módulo YouTube ({action}): {e}"

    async def update_system_prompt_with_memory(self):
        long_term = "MEMORY.md"
        memory_data = ""
        if os.path.exists(long_term):
            with open(long_term, "r", encoding="utf-8") as f:
                content = f.read()[:2000]
                if content.strip():
                    memory_data = "\n--- MEMÓRIA DE LONGO PRAZO ---\n" + content + "\n[IMPORTANTE: Use os fatos acima de forma implícita e natural. NÃO comente que você está lendo da memória de longo prazo, apenas saiba as informações.]\n"
                
        # Mantém a original e apenda a memória carregada no início do boot
        base_prompt = self.history[0].content.split("\n--- MEMÓRIA")[0]
        self.history[0] = ChatMessage(role="system", content=base_prompt + memory_data)

    async def check_compaction(self):
        """Mecanismo de Flush Stealth (OpenClaw) - Compactação da janela de contexto"""
        char_count = sum(len(msg.content) for msg in self.history if msg.content)
        
        if char_count > 15000:  # Limite de segurança arbitrário para flush
            console.print("[dim yellow][SISTEMA] Iniciando flush de memória silencioso (Compaction)...[/dim yellow]")
            
            # Remove temporariamente o prompt atual do usuário para protegê-lo da compactação
            last_user_msg = self.history.pop()
            hist_len_before = len(self.history)
            
            compaction_prompt = "A sessão está no limite de contexto. Você DEVE armazenar TODO O CONHECIMENTO CRUCIAL recém-aprendido nesta sessão usando MEMORY_SAVE_LONG_TERM ou MEMORY_SAVE_DAILY. Se não houver nada importante de longo prazo a guardar, responda única e puramente com o texto: NO_REPLY."
            
            self.history.append(ChatMessage(role="user", content=compaction_prompt))
            await self.ask(None, is_tool_response=True, silent=True)
            
            # Reverte o histórico e destrói todos os delírios e respostas de background geradas na compactação
            self.history = self.history[:hist_len_before]
            
            new_history = [self.history[0]]
            recent_msgs = self.history[1:][-4:]
            for msg in recent_msgs:
                # Trunca respostas gigantes do sistema das interações velhas para salvar peso
                if msg.content and "[SISTEMA:" in msg.content and len(msg.content) > 1000:
                    msg.content = msg.content[:1000] + "\n... [RESULTADO TRUNCADO PELO SISTEMA PARA POUPAR RAM]"
                new_history.append(msg)
                
            self.history = new_history
            self.history.append(last_user_msg)
            
            console.print("[dim green][SISTEMA] Contexto compactado e truncado de forma limpa![/dim green]")

    async def transcribe_audio(self, audio_path: str) -> str:
        """Envia o arquivo para a Mistral API para transcrição via voxtral-mini-latest"""
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            return ""
            
        console.print(f"[info]🎙️ Transcrevendo áudio recebido via Mistral Voxtral...[/info]")
        try:
            import aiohttp
            url = "https://api.mistral.ai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {api_key}"}
            
            with open(audio_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field('model', 'voxtral-mini-latest')
                # Precisamos passar com a chave 'file'
                form.add_field('file', f, filename=os.path.basename(audio_path))
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, data=form) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("text", "")
                        else:
                            console.print(f"[error]Erro na API de Transcrição: {await response.text()}[/error]")
                            return ""
        except Exception as e:
            console.print(f"[error]Exceção ao transcrever áudio: {e}[/error]")
            return ""

    async def ask(self, prompt: str = None, is_tool_response: bool = False, silent: bool = False):
        if not self.mistral_client:
            console.print("[warning]Mistral AI não configurado.[/warning]")
            return
            
        if prompt:
            self.history.append(ChatMessage(role="user", content=prompt))
            
        # Avalia sempre que o usuario manda uma mensagem real se precisa flushear contexto
        if not is_tool_response and not silent:
            await self.update_system_prompt_with_memory()
            await self.check_compaction()
        
        if not is_tool_response and not silent:
            console.print(f"\n[moltyclaw]{self.name}:[/moltyclaw]", end=" ")
        
        try:
            response_chunks = ""
            async_response = self.mistral_client.chat_stream(
                model="mistral-large-latest",
                messages=self.history
            )
            
            in_tool_mode = False
            buffer_txt = ""
            
            async for chunk in async_response:
                text = chunk.choices[0].delta.content
                if text:
                    response_chunks += text
                    # Esconde o bloco <tool> inteiro do usuário usando buffer inteligente
                    for char in text:
                        buffer_txt += char
                        if not in_tool_mode:
                            if "<tool>".startswith(buffer_txt):
                                if buffer_txt == "<tool>":
                                    in_tool_mode = True
                                    buffer_txt = ""
                            else:
                                if not silent:
                                    print(buffer_txt, end="", flush=True)
                                buffer_txt = ""
                        else:
                            if buffer_txt.endswith("</tool>"):
                                in_tool_mode = False
                                buffer_txt = ""
            
            if not is_tool_response and not silent:
                print()
            elif is_tool_response and not silent:
                print()
                
            if "NO_REPLY" in response_chunks:
                self.history.append(ChatMessage(role="assistant", content=response_chunks)) 
                return "Resumo efetuado."
            
            # Extrai e valida o JSON dentro de <tool>
            import json
            tool_match = re.search(r'<tool>\s*(.*?)\s*</tool>', response_chunks, re.DOTALL)
            
            # Adiciona a resposta do assistente no histórico DENTRO de try ANTES das novas chamadas de tool ou do retorno final
            self.history.append(ChatMessage(role="assistant", content=response_chunks))
            
            if tool_match:
                try:
                    json_str = tool_match.group(1).strip()
                    if json_str.startswith("```json"): json_str = json_str[7:]
                    elif json_str.startswith("```"): json_str = json_str[3:]
                    if json_str.endswith("```"): json_str = json_str[:-3]
                    
                    cmd_data = json.loads(json_str.strip())
                    action = cmd_data.get("action")
                    param = cmd_data.get("param", "")
                    
                    if action == "CMD":
                        console.print(f"\n[info]⚙️ Executando TERMINAL:[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description="Aguardando OS...", total=None)
                            result = await self.execute_terminal_command(param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado CMD] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action == "DDG_SEARCH":
                        console.print(f"\n[info]🦆 Executando Busca Nativa ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description="Pesquisando na DuckDuckGo API...", total=None)
                            
                            try:
                                from ddgs import DDGS
                                results = DDGS().text(param, max_results=5)
                                if not results:
                                    result = "Nenhum resultado encontrado."
                                else:
                                    result = "Resultados da Busca:\n"
                                    for idx, r in enumerate(results):
                                        result += f"{idx+1}. [{r['title']}]({r['href']})\nResumo: {r['body']}\n\n"
                            except Exception as e:
                                result = f"Erro na API DuckDuckGo: {str(e)}"
                                
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado DDG_SEARCH] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action in ["GOTO", "CLICK", "TYPE", "READ_PAGE", "SCREENSHOT", "INSPECT_PAGE"]:
                        if not silent: console.print(f"\n[info]🌐 Executando Browser ({action}):[/info] {param}")
                        result = await self.run_browser_action(action, param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado {action}] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action in ["READ_EMAILS", "SEND_EMAIL", "DELETE_EMAIL"]:
                        console.print(f"\n[info]📧 Módulo GMAIL ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Logando no Google Servers...", total=None)
                            result = await self.execute_gmail_action(action, param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado {action}] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action.startswith("MEMORY_"):
                        if not silent: console.print(f"\n[info]🧠 Módulo MEMORY ({action}):[/info] {param}")
                        result = await self.run_memory_action(action, param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado {action}] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action.startswith("SPOTIFY_"):
                        if not silent: console.print(f"\n[info]🎵 Módulo SPOTIFY ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Comunicando com Spotify API...", total=None)
                            result = await self.execute_spotify_action(action, param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado {action}] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action in ["WHATSAPP_SEND", "DISCORD_SEND", "TELEGRAM_SEND", "X_POST"]:
                        if not silent: 
                            if action == "X_POST":
                                console.print(f"\n[info]🌐 Módulo Social Envio ({action}):[/info] Destino -> Twitter Timeline")
                            else:
                                console.print(f"\n[info]🌐 Módulo Social Envio ({action}):[/info] Destino -> {param.split('|')[0] if '|' in param else param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Comunicando com provedor social...", total=None)
                            result = await self.execute_social_send(action, param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado {action}] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action.startswith("YOUTUBE_"):
                        if not silent: console.print(f"\n[info]▶️ Módulo YOUTUBE ({action}):[/info] {param}")
                        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                            progress.add_task(description=f"Baixando modelo temporal de Legendas do YouTube (CC)...", total=None)
                            result = await self.execute_youtube_action(action, param)
                        self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado {action}] -> {result}"))
                        return await self.ask(None, is_tool_response=True, silent=silent)
                        
                    elif action == "VOICE_REPLY":
                        parts = param.split("|", 1)
                        text = parts[0].strip()
                        target = parts[1].strip() if len(parts) > 1 else None
                        
                        if not silent: 
                            if target:
                                console.print(f"\n[info]🎙️ Módulo TTS (Gerando e Enviando Voz):[/info] Destino -> {target}")
                            else:
                                console.print(f"\n[info]🎙️ Módulo TTS (Gerando Voz):[/info] {text[:30]}...")
                                
                        import time
                        from pathlib import Path
                        temp_dir = Path("temp")
                        temp_dir.mkdir(exist_ok=True)
                        audio_path = temp_dir / f"molty_reply_{int(time.time())}.mp3"
                        # Utilizando edge-tts nativamente via asyncio para evitar problemas de escape no subprocesso
                        import edge_tts
                        
                        try:
                            communicate = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
                            await communicate.save(str(audio_path))
                        except Exception as e:
                            err_str = str(e)
                            console.print(f"[bold red]Erro edge-tts nativo:[/bold red] {err_str}")
                            self.history.append(ChatMessage(role="user", content=f"[SISTEMA: ERRO TTS] Falha ao gerar o arquivo mp3. Erro: {err_str}"))
                            return await self.ask(None, is_tool_response=True, silent=silent)
                        
                        if audio_path.exists():
                            if target:
                                # A IA mandou um Target junto... Isso significa que ela quer tentar ENVIAR pra frente ativamente
                                # Vamos descobrir de onde a mensagem original veio pra usar a ponte primária
                                dest = target
                                dest_clean = dest.replace("+", "").replace("-", "").replace(" ", "")
                                if len(dest_clean) > 10 and dest_clean.isdigit(): # Maioria numero Zap
                                    result = await self.execute_social_send("WHATSAPP_SEND", f"{dest} | | {audio_path.absolute()}")
                                elif len(dest_clean) in [18, 19] and dest_clean.isdigit(): # Maioria ID discord
                                    result = await self.execute_social_send("DISCORD_SEND", f"{dest} | | {audio_path.absolute()}")
                                else: # Telegram ou afins
                                    result = await self.execute_social_send("TELEGRAM_SEND", f"{dest} | | {audio_path.absolute()}")
                                    
                                self.history.append(ChatMessage(role="user", content=f"[SISTEMA: Resultado envio de VOZ ativo para {target}] -> {result}"))
                                return await self.ask(None, is_tool_response=True, silent=silent)
                            else:
                                return f"[AUDIO_REPLY: {audio_path.absolute()}]"
                        else:
                            console.print(f"[bold red]Erro edge-tts nativo:[/bold red] Arquivo não foi criado fisicamente no disco.")
                            self.history.append(ChatMessage(role="user", content=f"[SISTEMA: ERRO TTS] Falha desconhecida. O arquivo mp3 não foi criado."))
                            return await self.ask(None, is_tool_response=True, silent=silent)
                        
                except Exception as e:
                    err_msg = f"Erro no Parse do JSON da Tool: {str(e)} no bloco: {tool_match.group(1)}"
                    console.print(f"\n[error]{err_msg}[/error]")
                    self.history.append(ChatMessage(role="user", content=f"[SISTEMA: ERRO] {err_msg}. Corrija o JSON!"))
                    return await self.ask(None, is_tool_response=True, silent=silent)
                
            return response_chunks
            
        except Exception as e:
            err_msg = f"Erro ao comunicar com Mistral: {e}"
            console.print(f"[error]{err_msg}[/error]")
            return err_msg

async def interactive_shell():
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]🤖 MoltyClaw - Modo Full-Browser Ativado[/bold cyan]\n"
        "[dim]Agente interativo com capacidades de clicar, digitar e manter sessão.[/dim]",
        border_style="cyan"
    ))
    
    agent = MoltyClaw()
    # Inicializa o Browser Persistent Mode logo ao iniciar o CLI
    await agent.init_browser()
    
    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]Você[/bold blue]").strip()
            
            if user_input.lower() in ['sair', 'exit', 'quit']:
                console.print("[moltyclaw]MoltyClaw:[/moltyclaw] Fechando o navegador e desligando! 👋")
                await agent.close_browser()
                break
            
            if not user_input:
                continue
                
            # Interceptando comandos diretos
            if user_input.startswith("!cmd "):
                cmd = user_input[5:]
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
                    progress.add_task(description=f"Executando '{cmd}'...", total=None)
                    result = await agent.execute_terminal_command(cmd)
                console.print(Panel(result, title="[green]Terminal Output[/green]", border_style="green"))
                continue
                
            # Conversa padrão com a IA
            await agent.ask(user_input)
            
        except (KeyboardInterrupt, EOFError):
            console.print("\n[moltyclaw]MoltyClaw:[/moltyclaw] Processo interrompido.")
            await agent.close_browser()
            break
        except Exception:
            pass

if __name__ == "__main__":
    if os.name == 'nt':
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(interactive_shell())
