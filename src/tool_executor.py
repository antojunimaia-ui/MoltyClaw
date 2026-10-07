import os
import sys
import time
import re
import json
import asyncio
import subprocess
from pathlib import Path
from rich.progress import Progress, SpinnerColumn, TextColumn

from initializer import MOLTY_DIR
from skills import find_skill_by_name, load_skill_body
from integrations.gmail import execute_gmail_action
from integrations.spotify import execute_spotify_action
from integrations.youtube import execute_youtube_action


class ToolExecutor:
    def __init__(self, agent):
        self.agent = agent

    @property
    def console(self):
        return self.agent.console

    @property
    def name(self):
        return self.agent.name

    @property
    def base_dir(self):
        return self.agent.base_dir

    @property
    def workspace_dir(self):
        return self.agent.workspace_dir

    async def execute_terminal_command(self, command: str, timeout_seconds: int = 45) -> str:
        if os.environ.get("MOLTY_MODE", "private") == "public":
            self.console.print(f"[warning][{self.name}] Tentativa de uso de CMD intercedida pelo Modo Publico.[/warning]")
            return "Erro: O comando CMD está DESABILITADO no modo PUBLIC (ações de terminal bloqueadas por segurança)."

        self.console.print(f"[info][{self.name}] Executando comando:[/info] {command}")
        command = (command or "").strip()
        if not command:
            return "Comando vazio."

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        if sys.platform == "win32":
            env["PYTHONUTF8"] = "1"

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace_dir,
                env=env
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=float(timeout_seconds))
            except asyncio.TimeoutError:
                if sys.platform == "win32":
                    subprocess.run(f"taskkill /F /T /PID {process.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    try:
                        process.kill()
                    except Exception:
                        pass
                return f"[Timeout] O comando excedeu o limite de tempo de {timeout_seconds}s e foi encerrado."

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()

            clean_out = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', out_text)
            clean_err = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', err_text)

            res_parts = []
            if clean_out:
                res_parts.append(clean_out)
            if clean_err:
                res_parts.append(f"[STDERR]\n{clean_err}")
            if process.returncode != 0:
                res_parts.append(f"[Exit Code: {process.returncode}]")

            result_str = "\n".join(res_parts).strip()
            return result_str if result_str else "Comando executado com sucesso (sem saída no terminal)."

        except Exception as e:
            return f"Exceção ao executar comando: {e}"

    async def run_workspace_action(self, action: str, param: str) -> str:
        mem_dir = os.path.join(self.base_dir, "memory")
        os.makedirs(mem_dir, exist_ok=True)

        try:
            if action in ["FILE_WRITE", "FILE_APPEND"]:
                if " | " not in param:
                    return 'Erro: param precisa estar no formato "arquivo.ext | conteudo"'

                parts = param.split(" | ", 1)
                filepath, content = parts[0].strip(), parts[1]

                if ".." in filepath or os.path.isabs(filepath):
                    return "Erro: O caminho deve ser relativo ao workspace do agente."

                path = os.path.join(self.workspace_dir, filepath)
                os.makedirs(os.path.dirname(path), exist_ok=True)

                mode = "w" if action == "FILE_WRITE" else "a"
                with open(path, mode, encoding="utf-8") as f:
                    f.write(content + ("\n" if mode == "a" else ""))
                return f"✅ Arquivo {filepath} {'criado/sobrescrito' if mode == 'w' else 'atualizado (append)'} com sucesso!"

            elif action == "FILE_READ":
                filepath = param.strip()
                if ".." in filepath or os.path.isabs(filepath):
                    return "Erro: O caminho deve ser relativo."

                path = os.path.join(self.workspace_dir, filepath)
                if not os.path.exists(path):
                    return f"Arquivo '{filepath}' não encontrado no workspace."

                with open(path, "r", encoding="utf-8") as f:
                    return f.read()[:5000]

            elif action == "MEMORY_SEARCH":
                query = param.lower().strip()
                import memory_rag
                rag = memory_rag.HybridMemoryRAG(self.base_dir, self.workspace_dir, self.agent.get_embedding)
                search_res = await rag.search(query, top_k=5)

                if search_res:
                    res_texts = []
                    for score, p in search_res:
                        res_texts.append(f"[{p['file']}] Trecho: {p['text'][:150]}...")
                    return "Memórias mais relevantes encontradas:\n" + "\n".join(res_texts) + "\n\nUse FILE_READ se precisar ler o contexto inteiro de algum dos arquivos acima."
                return "Nenhuma memória semanticamente relevante encontrada."

            elif action == "SCHEDULE_TASK":
                if " | " not in param:
                    return 'Erro: Use "Nome do Job | Intervalo_Minutos | Payload do Prompt"'
                parts = param.split(" | ", 2)
                if len(parts) < 3:
                    return 'Erro: Use "Nome do Job | Intervalo_Minutos | Payload do Prompt"'
                name, interval, payload = parts[0].strip(), parts[1].strip(), parts[2].strip()
                job = self.agent.scheduler.add_job(name, "Agendado via IA", interval, payload)
                return f"✅ Tarefa '{name}' agendada com sucesso! ID: {job['id']}. Ela rodará a cada {interval} minutos de forma autônoma."

            elif action == "LIST_TASKS":
                jobs = self.agent.scheduler.jobs
                if not jobs:
                    return "Nenhuma tarefa agendada no momento."
                res = "### Tarefas Ativas:\n"
                for j in jobs:
                    status = "✅ Ativo" if j.get("enabled", True) else "❌ Desativado"
                    res += f"- **ID: {j['id']}** | {j['name']} ({j['interval']//60}min) | Status: {status}\n"
                return res

            elif action == "DELETE_TASK":
                job_id = param.strip()
                self.agent.scheduler.remove_job(job_id)
                return f"Tarefa {job_id} removida com sucesso (se existia)."

        except Exception as e:
            return f"Erro Módulo de Workspace: {e}"

        return f"Ação desconhecida de workspace: {action}"

    async def execute_github_action(self, action: str, param: str) -> str:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            return "ERRO: GITHUB_TOKEN não configurado no .env. Gere um token em https://github.com/settings/tokens"

        def _run_sync():
            try:
                from github import Github, GithubException
            except ImportError:
                return "ERRO: Biblioteca PyGithub não instalada. Execute: pip install PyGithub"

            g = Github(token)

            if action == "GITHUB_LIST_REPOS":
                try:
                    user = g.get_user(param.strip()) if param.strip() else g.get_user()
                    repos = list(user.get_repos())[:20]
                    lines = [f"📦 Repositórios de {user.login}:"]
                    for r in repos:
                        stars = f"⭐{r.stargazers_count}" if r.stargazers_count else ""
                        lines.append(f"  • {r.full_name} [{r.language or 'N/A'}] {stars}")
                    return "\n".join(lines)
                except GithubException as e:
                    return f"Erro ao listar repos: {e.data.get('message', str(e))}"

            elif action == "GITHUB_LIST_ISSUES":
                parts = [p.strip() for p in param.split("|")]
                repo_name = parts[0]
                state = "open"
                limit = 10
                for p in parts[1:]:
                    if p.startswith("state:"):
                        state = p.split(":", 1)[1].strip()
                    elif p.startswith("limit:"):
                        try:
                            limit = int(p.split(":", 1)[1].strip())
                        except Exception:
                            pass
                try:
                    repo = g.get_repo(repo_name)
                    issues = list(repo.get_issues(state=state))[:limit]
                    if not issues:
                        return f"Nenhuma issue {state} em {repo_name}."
                    lines = [f"🐛 Issues {state} em {repo_name}:"]
                    for i in issues:
                        lines.append(f"  #{i.number} [{i.state}] {i.title} — @{i.user.login}")
                    return "\n".join(lines)
                except GithubException as e:
                    return f"Erro ao listar issues: {e.data.get('message', str(e))}"

            elif action == "GITHUB_CREATE_ISSUE":
                parts = [p.strip() for p in param.split("|", 2)]
                if len(parts) < 2:
                    return "Uso: GITHUB_CREATE_ISSUE owner/repo | título | corpo opcional"
                repo_name, title = parts[0], parts[1]
                body = parts[2] if len(parts) > 2 else ""
                try:
                    repo = g.get_repo(repo_name)
                    issue = repo.create_issue(title=title, body=body)
                    return f"✅ Issue criada: #{issue.number} — {issue.title}\n🔗 {issue.html_url}"
                except GithubException as e:
                    return f"Erro ao criar issue: {e.data.get('message', str(e))}"

            elif action == "GITHUB_LIST_PRS":
                parts = [p.strip() for p in param.split("|")]
                repo_name = parts[0]
                state = "open"
                for p in parts[1:]:
                    if p.startswith("state:"):
                        state = p.split(":", 1)[1].strip()
                try:
                    repo = g.get_repo(repo_name)
                    prs = list(repo.get_pulls(state=state))[:10]
                    if not prs:
                        return f"Nenhum PR {state} em {repo_name}."
                    lines = [f"🔀 PRs {state} em {repo_name}:"]
                    for pr in prs:
                        lines.append(f"  #{pr.number} {pr.title} — @{pr.user.login} ({pr.head.ref} → {pr.base.ref})")
                    return "\n".join(lines)
                except GithubException as e:
                    return f"Erro ao listar PRs: {e.data.get('message', str(e))}"

            elif action == "GITHUB_GET_PR":
                parts = [p.strip() for p in param.split("|")]
                if len(parts) < 2:
                    return "Uso: GITHUB_GET_PR owner/repo | número"
                try:
                    repo = g.get_repo(parts[0])
                    pr = repo.get_pull(int(parts[1]))
                    files = [f.filename for f in pr.get_files()]
                    return (
                        f"🔀 PR #{pr.number}: {pr.title}\n"
                        f"Estado: {pr.state} | Merge: {'✅' if pr.merged else '❌'}\n"
                        f"Autor: @{pr.user.login} | {pr.head.ref} → {pr.base.ref}\n"
                        f"Arquivos modificados ({len(files)}): {', '.join(files[:15])}\n"
                        f"Descrição: {(pr.body or 'Sem descrição.')[:500]}\n"
                        f"🔗 {pr.html_url}"
                    )
                except GithubException as e:
                    return f"Erro ao obter PR: {e.data.get('message', str(e))}"

            elif action == "GITHUB_CREATE_COMMENT":
                parts = [p.strip() for p in param.split("|", 2)]
                if len(parts) < 3:
                    return "Uso: GITHUB_CREATE_COMMENT owner/repo | número | comentário"
                try:
                    repo = g.get_repo(parts[0])
                    issue = repo.get_issue(int(parts[1]))
                    comment = issue.create_comment(parts[2])
                    return f"✅ Comentário adicionado na #{parts[1]}: {comment.html_url}"
                except GithubException as e:
                    return f"Erro ao comentar: {e.data.get('message', str(e))}"

            elif action == "GITHUB_GET_FILE":
                parts = [p.strip() for p in param.split("|")]
                if len(parts) < 2:
                    return "Uso: GITHUB_GET_FILE owner/repo | caminho/arquivo | branch_opcional"
                try:
                    repo = g.get_repo(parts[0])
                    kwargs = {}
                    if len(parts) >= 3:
                        kwargs["ref"] = parts[2]
                    content = repo.get_contents(parts[1], **kwargs)
                    decoded = content.decoded_content.decode("utf-8", errors="replace")
                    return f"📄 {parts[1]} ({content.encoding}):\n```\n{decoded[:3000]}\n```"
                except GithubException as e:
                    return f"Erro ao obter arquivo: {e.data.get('message', str(e))}"

            elif action == "GITHUB_LIST_COMMITS":
                parts = [p.strip() for p in param.split("|")]
                repo_name = parts[0]
                sha = parts[1] if len(parts) > 1 else None
                limit = 10
                try:
                    limit = int(parts[2]) if len(parts) > 2 else 10
                except Exception:
                    pass
                try:
                    repo = g.get_repo(repo_name)
                    kwargs = {}
                    if sha:
                        kwargs["sha"] = sha
                    commits = list(repo.get_commits(**kwargs))[:limit]
                    lines = [f"📝 Commits em {repo_name}{' (' + sha + ')' if sha else ''}:"]
                    for c in commits:
                        msg = c.commit.message.split("\n")[0][:70]
                        lines.append(f"  {c.sha[:7]} — {msg} (@{c.commit.author.name})")
                    return "\n".join(lines)
                except GithubException as e:
                    return f"Erro ao listar commits: {e.data.get('message', str(e))}"

            return f"Ação GitHub desconhecida: {action}"

        return await asyncio.get_event_loop().run_in_executor(None, _run_sync)

    async def execute_social_send(self, action: str, param: str) -> str:
        if action == "X_POST":
            text = param.strip()
            if len(text) > 280:
                text = text[:277] + "..."

            import tweepy
            try:
                client = tweepy.Client(
                    bearer_token=os.getenv("TWITTER_BEARER_TOKEN"),
                    consumer_key=os.getenv("TWITTER_API_KEY"),
                    consumer_secret=os.getenv("TWITTER_API_SECRET"),
                    access_token=os.getenv("TWITTER_ACCESS_TOKEN"),
                    access_token_secret=os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
                )
                if not os.getenv("TWITTER_API_KEY"):
                    return "Erro: Token de Twitter ausente."

                client.create_tweet(text=text)
                return "Tweet disparado ativamente com sucesso na timeline do X!"
            except Exception as ex:
                return f"Erro na API do Twitter (X) v2: {ex}"

        if action in ["BLUESKY_POST", "BLUESKY_GET_PROFILE"]:
            try:
                from atproto import Client
                handle = os.getenv("BLUESKY_HANDLE", "").lstrip("@")
                password = os.getenv("BLUESKY_APP_PASSWORD")
                if not handle or not password:
                    return "Erro: Credenciais do Bluesky ausentes no .env."

                client = Client()
                await asyncio.to_thread(client.login, handle, password)

                if action == "BLUESKY_POST":
                    text = param.strip()
                    if len(text) > 300:
                        text = text[:297] + "..."
                    await asyncio.to_thread(client.send_post, text=text)
                    return "Skeet postado com sucesso no Bluesky!"

                elif action == "BLUESKY_GET_PROFILE":
                    target = param.strip() or handle
                    profile = await asyncio.to_thread(client.get_profile, actor=target)
                    return (
                        f"Perfil de {profile.handle}:\n"
                        f"- Nome: {profile.display_name or 'N/A'}\n"
                        f"- Seguidores: {profile.followers_count}\n"
                        f"- Seguindo: {profile.follows_count}\n"
                        f"- Posts: {profile.posts_count}\n"
                        f"- Bio: {(profile.description or '').strip()[:150]}"
                    )
            except Exception as e:
                import traceback
                return f"Erro na integração Bluesky: {str(e)}\n{traceback.format_exc() if 'DEBUG' in os.environ else ''}"

        parts = param.split("|")
        target = parts[0].strip()
        text = parts[1].strip() if len(parts) > 1 else ""
        file_path = parts[2].strip() if len(parts) > 2 else ""

        if not text and not file_path:
            return "Erro: Formato inválido. Use [destination | text opcional | file_path opcional]. Providencie pelo menos text ou file."

        try:
            import aiohttp
            if action == "TELEGRAM_SEND":
                token = os.getenv("TELEGRAM_TOKEN")
                if not token:
                    return "Erro: TELEGRAM_TOKEN ausente."
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
                        if text:
                            form.add_field("caption", text)
                        form.add_field(file_field, open(file_path, "rb"), filename=os.path.basename(file_path))

                        async with session.post(url, data=form) as resp:
                            if resp.status == 200:
                                return f"Arquivo/Mensagem enviada com sucesso no Telegram para {target}."
                            return f"Erro do Telegram API (HTTP {resp.status}): {await resp.text()}"
                    else:
                        url = f"https://api.telegram.org/bot{token}/sendMessage"
                        async with session.post(url, json={"chat_id": target, "text": text}) as resp:
                            if resp.status == 200:
                                return f"Mensagem enviada com sucesso no Telegram para {target}."
                            return f"Erro do Telegram API (HTTP {resp.status}): {await resp.text()}"

            elif action == "DISCORD_SEND":
                token = os.getenv("DISCORD_TOKEN")
                if not token:
                    return "Erro: DISCORD_TOKEN ausente."
                url_dm = "https://discord.com/api/v10/users/@me/channels"
                headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
                async with aiohttp.ClientSession() as session:
                    async with session.post(url_dm, headers=headers, json={"recipient_id": target}) as resp_dm:
                        if resp_dm.status != 200:
                            return f"Erro abrindo DM Discord: {await resp_dm.text()}"
                        dm_data = await resp_dm.json()
                        channel_id = dm_data["id"]
                        url_msg = f"https://discord.com/api/v10/channels/{channel_id}/messages"

                        if file_path and os.path.exists(file_path):
                            form = aiohttp.FormData()
                            payload = {}
                            if text:
                                payload["content"] = text
                            form.add_field("payload_json", json.dumps(payload), content_type="application/json")
                            form.add_field("files[0]", open(file_path, "rb"), filename=os.path.basename(file_path))
                            headers_file = {"Authorization": f"Bot {token}"}

                            async with session.post(url_msg, headers=headers_file, data=form) as resp_msg:
                                if resp_msg.status == 200:
                                    return "Arquivo/Mensagem enviada no Discord com sucesso."
                                return f"Erro Discord (HTTP {resp_msg.status}): {await resp_msg.text()}"
                        else:
                            async with session.post(url_msg, headers=headers, json={"content": text}) as resp_msg:
                                if resp_msg.status == 200:
                                    return "Mensagem enviada no Discord com sucesso."
                                return f"Erro Discord (HTTP {resp_msg.status}): {await resp_msg.text()}"

            elif action == "WHATSAPP_SEND":
                async with aiohttp.ClientSession() as session:
                    if not target.endswith("@c.us"):
                        target = target.replace("+", "").replace("-", "").replace(" ", "") + "@c.us"

                    payload = {"to": target, "message": text}
                    if file_path and os.path.exists(file_path):
                        payload["mediaPath"] = os.path.abspath(file_path)

                    async with session.post("http://localhost:8081/send_whatsapp", json=payload) as resp:
                        if resp.status == 200:
                            return "Mensagem engatilhada e enviada via WhatsApp Bridge Node."
                        return f"O Bridge do WhatsApp reportou erro ou nao esta rodando na porta 8081. (HTTP {resp.status})"

        except Exception as e:
            return f"Exceção interna no módulo Social: {e}"

        return f"Ação social desconhecida: {action}"

    async def execute_whatsapp_read(self, action: str, param: str) -> str:
        import aiohttp
        bridge_base = "http://localhost:8081"

        try:
            async with aiohttp.ClientSession() as session:
                if action == "WHATSAPP_GET_CONTACTS":
                    async with session.get(f"{bridge_base}/get_contacts", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            return f"Erro ao buscar contatos (HTTP {resp.status}): {await resp.text()}"
                        data = await resp.json()
                        contacts = data.get("contacts", [])
                        if not contacts:
                            return "Nenhum contato encontrado na agenda do WhatsApp."
                        lines = [f"📋 **{len(contacts)} contatos encontrados:**"]
                        for c in contacts:
                            name = c.get("name") or c.get("pushname") or c.get("number", "?")
                            number = c.get("number", "")
                            cid = c.get("id", "")
                            lines.append(f"- {name} | número: {number} | id: {cid}")
                        return "\n".join(lines)

                elif action == "WHATSAPP_GET_CHATS":
                    async with session.get(f"{bridge_base}/get_chats", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            return f"Erro ao buscar chats (HTTP {resp.status}): {await resp.text()}"
                        data = await resp.json()
                        chats = data.get("chats", [])
                        if not chats:
                            return "Nenhuma conversa encontrada no WhatsApp."
                        lines = [f"💬 **{len(chats)} conversas recentes:**"]
                        for c in chats:
                            name = c.get("name", "?")
                            cid = c.get("id", "")
                            unread = c.get("unreadCount", 0)
                            last = c.get("lastMessage")
                            unread_tag = f" 🔴 {unread} não lida(s)" if unread > 0 else ""
                            if last:
                                import datetime
                                ts = last.get("timestamp", 0)
                                dt = datetime.datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else ""
                                direction = "→" if last.get("fromMe") else "←"
                                body = last.get("body", "")[:80]
                                msg_type = last.get("type", "chat")
                                if msg_type != "chat":
                                    body = f"[{msg_type}]" + (f" {body}" if body else "")
                                lines.append(f"- **{name}**{unread_tag} | id: {cid}\n  {direction} [{dt}] {body}")
                            else:
                                lines.append(f"- **{name}**{unread_tag} | id: {cid}")
                        return "\n".join(lines)

                elif action == "WHATSAPP_GET_MESSAGES":
                    parts = param.split("|")
                    chat_id = parts[0].strip()
                    limit = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 20

                    if chat_id and not chat_id.endswith("@c.us") and not chat_id.endswith("@g.us"):
                        chat_id = chat_id.replace("+", "").replace("-", "").replace(" ", "") + "@c.us"

                    payload = {"chat_id": chat_id, "limit": min(limit, 50)}
                    async with session.post(
                        f"{bridge_base}/get_chat_messages",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=20)
                    ) as resp:
                        if resp.status != 200:
                            return f"Erro ao buscar mensagens (HTTP {resp.status}): {await resp.text()}"
                        data = await resp.json()
                        messages = data.get("messages", [])
                        chat_name = data.get("chat_name", chat_id)
                        if not messages:
                            return f"Nenhuma mensagem encontrada na conversa com {chat_name}."
                        lines = [f"📨 **Últimas {len(messages)} mensagens com {chat_name}:**"]
                        for m in messages:
                            import datetime
                            ts = m.get("timestamp", 0)
                            dt = datetime.datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else ""
                            direction = "Você" if m.get("fromMe") else (m.get("author") or chat_name)
                            body = m.get("body", "")
                            msg_type = m.get("type", "chat")
                            if msg_type != "chat" and not body:
                                body = f"[{msg_type}]"
                            elif msg_type != "chat":
                                body = f"[{msg_type}] {body}"
                            lines.append(f"[{dt}] **{direction}**: {body}")
                        return "\n".join(lines)

                else:
                    return f"Ação desconhecida: {action}"

        except aiohttp.ClientConnectorError:
            return "Erro: O bridge do WhatsApp (porta 8081) não está acessível. Certifique-se de que o WhatsApp está conectado."
        except Exception as e:
            return f"Exceção ao consultar bridge do WhatsApp: {e}"

    async def execute_tool(
        self,
        action: str,
        param: str,
        cmd_data: dict,
        silent: bool = False,
        stream_callback=None,
        tool_callback=None
    ) -> str:
        # ─── VERIFICAÇÃO DE PERMISSÕES ───────────────────────────────────
        if not self.agent._is_tool_allowed(action):
            error_msg = f"❌ ACESSO NEGADO: O agente '{self.name}' não tem permissão para usar a ferramenta '{action}'."
            self.console.print(f"[error]{error_msg}[/error]")
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Erro de Permissão] -> {error_msg}"})
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        if action == "MCP_TOOL":
            mcp_server = cmd_data.get("server")
            mcp_tool = cmd_data.get("tool")
            mcp_params = cmd_data.get("params", {})

            self.console.print(f"\n[info]🔌 Módulo MCP Externo ({mcp_server}):[/info] Rodando Tool '{mcp_tool}'")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Comunicando via StdioProtocol ao servidor...", total=None)
                if self.agent.mcp_hub:
                    result = await self.agent.mcp_hub.call_tool(mcp_server, mcp_tool, mcp_params)
                else:
                    result = "Falha: MCPHub não estava ativo ou não importou as bibliotecas."

            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado MCP Tool {mcp_tool}] ->\n{result}"})
            if tool_callback:
                await tool_callback(f"[MCP] {mcp_tool}")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "CMD":
            self.console.print(f"\n[info]⚙️ Executando TERMINAL:[/info] {param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Aguardando OS...", total=None)
                result = await self.execute_terminal_command(param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado CMD] -> {result}"})
            if tool_callback:
                await tool_callback(f"[CMD] {param}")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "FS_LIST":
            self.console.print(f"\n[info]📂 Listando Diretório (FS Nativo):[/info] {param or '~'}")
            try:
                target_path = (os.path.expanduser(param.strip()) if param and param.strip() else os.path.expanduser("~"))
                if not os.path.isabs(target_path):
                    result = f"[FS_LIST] Erro: o caminho deve ser absoluto. Recebido: '{param}'"
                elif not os.path.exists(target_path):
                    result = f"[FS_LIST] Caminho não encontrado: {target_path}"
                else:
                    entries = []
                    try:
                        with os.scandir(target_path) as it:
                            for entry in it:
                                try:
                                    stat = entry.stat(follow_symlinks=True)
                                    kind = "DIR " if entry.is_dir(follow_symlinks=True) else "FILE"
                                    size = f" ({stat.st_size:,} bytes)" if kind == "FILE" else ""
                                    entries.append((kind, entry.name, size))
                                except Exception:
                                    entries.append(("???", entry.name, ""))
                    except PermissionError:
                        result = f"[FS_LIST] Acesso negado: {target_path}"
                        self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado FS_LIST] -> {result}"})
                        if tool_callback:
                            await tool_callback(f"[FS_LIST] {param}")
                        return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

                    dirs = sorted([(n, s) for k, n, s in entries if k == "DIR "], key=lambda x: x[0].lower())
                    files = sorted([(n, s) for k, n, s in entries if k == "FILE"], key=lambda x: x[0].lower())
                    parent = os.path.dirname(target_path)

                    lines = [f"📁 {target_path}"]
                    if parent != target_path:
                        lines.append(f"  ⬆️  .. ({parent})")
                    for name, _ in dirs:
                        lines.append(f"  📁 {name}/")
                    for name, size in files:
                        lines.append(f"  📄 {name}{size}")
                    lines.append(f"\nTotal: {len(dirs)} pasta(s), {len(files)} arquivo(s)")
                    result = "\n".join(lines)
            except Exception as e:
                result = f"[FS_LIST] Erro inesperado: {str(e)}"

            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado FS_LIST] -> {result}"})
            if tool_callback:
                await tool_callback(f"[FS_LIST] {param}")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "DDG_SEARCH":
            self.console.print(f"\n[info]🦆 Executando Busca Nativa ({action}):[/info] {param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
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

            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado DDG_SEARCH] -> {result}"})
            if tool_callback:
                await tool_callback(f"[SEARCH] {param}")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "CANVAS_UPDATE":
            try:
                parts = param.split('|', 2)
                if len(parts) == 3:
                    artifact_id = parts[0].strip()
                    artifact_type = parts[1].strip()
                    content = parts[2].strip()

                    canvas_dir = os.path.join(self.base_dir, "canvas")
                    os.makedirs(canvas_dir, exist_ok=True)

                    ext = "md"
                    if "html" in artifact_type.lower(): ext = "html"
                    elif "svg" in artifact_type.lower(): ext = "svg"
                    elif "react" in artifact_type.lower(): ext = "jsx"
                    elif "css" in artifact_type.lower(): ext = "css"
                    elif "js" in artifact_type.lower(): ext = "js"

                    fpath = os.path.join(canvas_dir, f"{artifact_id}.{ext}")
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)

                    result = f"✅ Canvas {artifact_id}.{ext} atualizado e exibido no painel visual."
                    if tool_callback:
                        await tool_callback(f"[CANVAS] Atualizando {artifact_id}...")
                    if stream_callback:
                        await stream_callback(f"\n<!-- MOLTY_CANVAS_SYNC:{self.agent.agent_id}:{artifact_id}:{ext} -->\n")
                else:
                    result = "Erro: Formato incorreto. Use: id | tipo | conteudo"
            except Exception as e:
                result = f"Erro na renderização do Canvas: {str(e)}"

            self.agent.history.append({"role": "user", "content": f"[SISTEMA: CANVAS_UPDATE] -> {result}"})
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "SESSION_SPAWN":
            self.console.print(f"\n[info]🤖 Delegando Tarefa ({action}):[/info] {param}")
            if tool_callback:
                await tool_callback(f"[SESSION_SPAWN] {param[:30]}")

            try:
                parts = param.split('|', 1)
                if len(parts) == 2:
                    sub_id = parts[0].strip()
                    task_text = parts[1].strip()

                    cfg_path = os.path.join(MOLTY_DIR, "agents", sub_id, "config.json")
                    if not os.path.exists(cfg_path):
                        result = f"Erro: Sub-Agente '{sub_id}' não existe ou não foi configurado."
                    else:
                        with open(cfg_path, 'r', encoding='utf-8') as f:
                            scfg = json.load(f)

                        import subagent_registry as _sreg
                        run_id = _sreg.new_run_id()
                        run = _sreg.SubagentRun(
                            run_id=run_id,
                            agent_id=sub_id,
                            task=task_text,
                            requester_id=self.agent.agent_id,
                            label=scfg.get("name", sub_id),
                        )
                        _sreg.register(run)

                        _reply_cb = self.agent._current_reply_callback
                        _agent_label = scfg.get('name', sub_id)

                        async def _run_subagent_bg(_run=run, _scfg=scfg, _reply_cb=_reply_cb, _label=_agent_label):
                            _run.status = "running"
                            _run.started_at = time.time()
                            self.console.print(f"[dim]▶ Subagente '{_run.agent_id}' (run={_run.run_id}) iniciado em background[/dim]")
                            try:
                                env_path = os.path.join(MOLTY_DIR, "agents", _run.agent_id, ".env")
                                if os.path.exists(env_path):
                                    from dotenv import load_dotenv
                                    load_dotenv(env_path, override=True)

                                old_prov = os.environ.get("MOLTY_PROVIDER")
                                os.environ["MOLTY_PROVIDER"] = _scfg.get("provider", os.getenv("MOLTY_PROVIDER", "mistral"))

                                from moltyclaw import MoltyClaw
                                sub_agent = MoltyClaw(name=_label, agent_id=_run.agent_id)
                                _run.agent_instance = sub_agent

                                sub_reply = await sub_agent.ask(_run.task, silent=True)
                                await sub_agent.close_browser()

                                if old_prov:
                                    os.environ["MOLTY_PROVIDER"] = old_prov
                                elif "MOLTY_PROVIDER" in os.environ:
                                    del os.environ["MOLTY_PROVIDER"]

                                _run.status = "done"
                                _run.result = sub_reply
                                _run.ended_at = time.time()
                                duration = round(_run.ended_at - _run.started_at, 1)
                                self.console.print(f"[bold green]✅ Subagente '{_run.agent_id}' (run={_run.run_id}) concluído em {duration}s[/bold green]")

                                if _reply_cb:
                                    announce = f"✅ *[{_label}]* concluiu a tarefa em {duration}s:\n\n{sub_reply}"
                                    await _reply_cb(announce)

                            except Exception as _e:
                                _run.status = "error"
                                _run.error = str(_e)
                                _run.ended_at = time.time()
                                self.console.print(f"[bold red]❌ Subagente '{_run.agent_id}' (run={_run.run_id}) falhou: {_e}[/bold red]")
                                if _reply_cb:
                                    await _reply_cb(f"❌ Sub-Agente [{_label}] encontrou um erro: {_e}")

                        asyncio.create_task(_run_subagent_bg())
                        result = f"✅ Sub-Agente [{_agent_label}] iniciado em background (run_id={run_id})."
                else:
                    result = "Erro: Formato incorreto. Use 'id_do_agente | tarefa_detalhada'."
            except Exception as e:
                result = f"Erro ao executar SESSION_SPAWN: {e}"

            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "SESSION_LIST":
            import subagent_registry as _sreg
            result = _sreg.summary()
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado SESSION_LIST] ->\n{result}"})
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "SESSION_SEND":
            try:
                parts = param.split('|', 1)
                if len(parts) == 2:
                    run_id = parts[0].strip()
                    message = parts[1].strip()
                    import subagent_registry as _sreg
                    run = _sreg.get(run_id)
                    if run and run.status == "running" and getattr(run, "agent_instance", None):
                        run.agent_instance.history.append({"role": "user", "content": f"[INJEÇÃO DO MESTRE]: {message}"})
                        result = f"Mensagem enviada com sucesso para a sessão {run_id}. O sub-agente vai ler no próximo turno de raciocínio interno."
                    else:
                        result = f"Erro: Sessão {run_id} não encontrada ou não está mais rodando."
                else:
                    result = "Erro: Formato incorreto. Use 'id_sessao | mensagem_para_ele'."
            except Exception as e:
                result = f"Erro ao executar SESSION_SEND: {e}"
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado SESSION_SEND] -> {result}"})
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "SESSION_HISTORY":
            run_id = param.strip()
            import subagent_registry as _sreg
            run = _sreg.get(run_id)
            if run and getattr(run, "agent_instance", None):
                log = []
                for m in run.agent_instance.history:
                    content_str = m.get('content', '')
                    if len(content_str) > 500: content_str = content_str[:500] + "...(truncado)"
                    log.append(f"[{m.get('role', 'unknown').upper()}]: {content_str}")
                result = f"--- HISTÓRICO DA SESSÃO {run_id} ({run.agent_id}) ---\n" + "\n\n".join(log)
            else:
                result = f"Erro: Sessão {run_id} não encontrada ou a instância foi destruída."
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado SESSION_HISTORY] ->\n{result}"})
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action in ["OPEN_BROWSER", "GOTO", "CLICK", "TYPE", "READ_PAGE", "SCREENSHOT", "INSPECT_PAGE", "PRESS_ENTER", "PRESS_KEY", "SCROLL_DOWN"]:
            if not silent:
                self.console.print(f"\n[info]🌐 Executando Browser ({action}):[/info] {param}")
            result = await self.agent.browser.run_action(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}] {param[:30]}")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action in ["READ_EMAILS", "SEND_EMAIL", "DELETE_EMAIL"]:
            self.console.print(f"\n[info]📧 Módulo GMAIL ({action}):[/info] {param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Logando no Google Servers...", total=None)
                result = await execute_gmail_action(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action.startswith("FILE_") or action.startswith("MEMORY_"):
            if not silent:
                self.console.print(f"\n[info]📂 Workspace ({action}):[/info] {param[:30]}")
            result = await self.run_workspace_action(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "SKILL_USE":
            self.console.print(f"\n[info]🧩 Ativando SKILL:[/info] {param}")
            skill = find_skill_by_name(self.agent.skills, param)
            if not skill:
                result = f"ERRO: A skill '{param}' não foi encontrada ou não está instalada."
            elif not skill.eligible:
                result = f"ERRO: A skill '{param}' não pode ser carregada: {skill.eligibility_reason}"
            else:
                body = load_skill_body(skill)
                result = f"OK: Skill '{skill.name}' ativada com sucesso!\n\n--- INSTRUÇÕES DA SKILL ---\n{body}"

            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Ativação de Skill] -> {result}"})
            if tool_callback:
                await tool_callback(f"[SKILL] {param}")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action.startswith("SPOTIFY_"):
            if not silent:
                self.console.print(f"\n[info]🎵 Módulo SPOTIFY ({action}):[/info] {param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Comunicando com Spotify API...", total=None)
                result = await execute_spotify_action(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action.startswith("GITHUB_"):
            if not silent:
                self.console.print(f"\n[info]🐙 Módulo GITHUB ({action}):[/info] {param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Comunicando com GitHub API...", total=None)
                result = await self.execute_github_action(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action in ["WHATSAPP_SEND", "DISCORD_SEND", "TELEGRAM_SEND", "X_POST", "BLUESKY_POST", "BLUESKY_GET_PROFILE"]:
            if not silent:
                if action == "X_POST":
                    self.console.print(f"\n[info]🌐 Módulo Social Envio ({action}):[/info] Destino -> Twitter Timeline")
                elif action.startswith("BLUESKY"):
                    self.console.print(f"\n[info]🦋 Módulo Bluesky ({action}):[/info] {param}")
                else:
                    self.console.print(f"\n[info]🌐 Módulo Social Envio ({action}):[/info] Destino -> {param.split('|')[0] if '|' in param else param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Comunicando com provedor social...", total=None)
                result = await self.execute_social_send(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action in ["WHATSAPP_GET_CONTACTS", "WHATSAPP_GET_CHATS", "WHATSAPP_GET_MESSAGES"]:
            if not silent:
                self.console.print(f"\n[info]📱 WhatsApp Leitura ({action}):[/info] {param or ''}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Consultando bridge do WhatsApp...", total=None)
                result = await self.execute_whatsapp_read(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] ->\n{result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "YOUTUBE_SUMMARIZE":
            if not silent:
                self.console.print(f"\n[info]▶️ Módulo YOUTUBE ({action}):[/info] {param}")
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=self.console) as progress:
                progress.add_task(description="Baixando modelo temporal de Legendas do YouTube (CC)...", total=None)
                result = await execute_youtube_action(action, param)
            self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado {action}] -> {result}"})
            if tool_callback:
                await tool_callback(f"[{action}]")
            return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        elif action == "VOICE_REPLY":
            parts = param.split("|", 1)
            text = parts[0].strip()
            target = parts[1].strip() if len(parts) > 1 else None

            if not silent:
                if target:
                    self.console.print(f"\n[info]🎙️ Módulo TTS (Gerando e Enviando Voz):[/info] Destino -> {target}")
                else:
                    self.console.print(f"\n[info]🎙️ Módulo TTS (Gerando Voz):[/info] {text[:30]}...")

            temp_dir = Path(os.path.join(MOLTY_DIR, "temp"))
            temp_dir.mkdir(exist_ok=True)
            audio_path = temp_dir / f"molty_reply_{int(time.time())}.mp3"
            import edge_tts

            try:
                communicate = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
                await communicate.save(str(audio_path))
            except Exception as e:
                err_str = str(e)
                self.console.print(f"[bold red]Erro edge-tts nativo:[/bold red] {err_str}")
                self.agent.history.append({"role": "user", "content": f"[SISTEMA: ERRO TTS] Falha ao gerar o arquivo mp3. Erro: {err_str}"})
                return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

            if audio_path.exists():
                if target and target.strip().upper() not in ["SEU_ZAP_ID_AQUI", "TELEGRAM", "DISCORD", "WHATSAPP", "AQUI", "AQUI MESMO"]:
                    dest = target
                    dest_clean = dest.replace("+", "").replace("-", "").replace(" ", "")
                    if len(dest_clean) > 10 and dest_clean.isdigit():
                        result = await self.execute_social_send("WHATSAPP_SEND", f"{dest} | | {audio_path.absolute()}")
                    elif len(dest_clean) in [18, 19] and dest_clean.isdigit():
                        result = await self.execute_social_send("DISCORD_SEND", f"{dest} | | {audio_path.absolute()}")
                    else:
                        result = await self.execute_social_send("TELEGRAM_SEND", f"{dest} | | {audio_path.absolute()}")

                    self.agent.history.append({"role": "user", "content": f"[SISTEMA: Resultado envio de VOZ ativo para {target}] -> {result}"})
                    if tool_callback:
                        await tool_callback(f"[AUDIO_SENT_TO] {target}")
                    return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)
                else:
                    return f"[AUDIO_REPLY: {audio_path.absolute()}]"
            else:
                self.console.print("[bold red]Erro edge-tts nativo:[/bold red] Arquivo não foi criado fisicamente no disco.")
                self.agent.history.append({"role": "user", "content": "[SISTEMA: ERRO TTS] Falha desconhecida. O arquivo mp3 não foi criado."})
                return await self.agent.ask(None, is_tool_response=True, silent=silent, stream_callback=stream_callback, tool_callback=tool_callback)

        return f"Ação desconhecida: {action}"
