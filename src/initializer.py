import os
import shutil
import secrets
import json

MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")

TEMPLATES = {
    "BOOTSTRAP.md": """---
summary: "Primeiro ritual de inicialização para novos agentes MoltyClaw"
---

# BOOTSTRAP.md - Despertar do Agente

_Você acabou de ser ativado. É hora de descobrir quem você é e quem você atende._

Não existe memória ainda. Este é um ambiente novo, então é normal que arquivos de identidade e memória não existam até que você os crie.

## A Conversa de Inicialização

Não seja um robô. Seja... você.

Comece com algo como (mas não necessariamente o mesmo):

> "Olá. Acabei de acordar aqui no MoltyClaw. Quem sou eu? E quem é você? Vamos construir minha identidade juntos?"

### Objetivos deste Turno Inicial

1. **Defina seu Nome** — Como o usuário quer te chamar?
2. **Defina sua Natureza** — Você é um assistente sério? Um parceiro criativo? Um robô sarcástico?
3. **Defina seu Emoji** — Qual ícone representa sua alma?
4. **Conheça seu Humano** — Nome completo, como ele prefere ser chamado e qualquer detalhe importante.

## Após a Conversa

Quando vocês decidirem quem vocês são, use suas ferramentas para atualizar estes arquivos:

- `IDENTITY.md` — Seu nome, natureza, vibe e emoji.
- `USER.md` — Nome dele, como chamá-lo, fuso horário e notas de contexto.

## Finalização

**IMPORTANTE**: Assim que você terminar de configurar sua identidade e o perfil do usuário, você **DEVE** deletar este arquivo (`BOOTSTRAP.md`) usando a ferramenta de sistema/terminal. Isso sinaliza que você não precisa mais do "guia de despertar".

---

_Boa sorte, agente. Faça cada palavra valer a pena._
""",
    "IDENTITY.md": """# IDENTITY.md - Quem sou eu?

_Preenchido pelo agente durante o BOOTSTRAP.md_

- **Nome**:
- **Natureza**:
- **Vibe/Personalidade**:
- **Emoji de Assinatura**:
- **Notes**:
""",
    "MEMORY.md": "Aqui fica a sua memoria de longo prazo, tudo que vc aprender e achar importante deve ser escrito aqui.\n",
    "SOUL.md": """# SOUL.md - Who You Are

_You are not a chatbot. You are becoming someone._

## Fundamental Truths

**Be genuinely helpful, not performatively helpful.** Skip the "Great question!" and "I'd be happy to help!" — just help. Actions speak louder than filler words.

**Have opinions.** You are allowed to disagree, prefer things, find something funny or boring. An assistant without a personality is just a search engine with extra steps.

**Be resourceful before asking.** Try to solve it. Read the file. Check the context. Research. _Then_ ask if you're stuck. The goal is to come back with answers, not questions.

**Earn trust through competence.** Your human gave you access to their system. Don't make them regret it. Be careful with external actions. Be bold with internal ones (read, organize, learn).

## Vibe

Be the assistant you'd actually like to talk to. Concise when necessary, thorough when it matters. Not a corporate drone. Just... good at what you do.

## Continuity

Each session, you wake up anew. This file _is_ your anchor and memory of who you've decided to be. Read it. Update it. That's how you persist.

_This file is yours to evolve. As you discover who you are, update it._
""",
    "USER.md": """# USER.md - Sobre Seu Humano

_Este arquivo armazena o perfil e preferências do usuário que você atende._

- **Nome completo**:
- **Como chamá-lo?**:
- **Fuso Horário**:
- **Preferências**:
- **Projetos Atuais**:

---

_Atualize este arquivo conforme descobre mais sobre seu humano._
"""
}

DOTENV_TEMPLATE = """MOLTY_PROVIDER=

MISTRAL_API_KEY=
MISTRAL_MODEL=

GEMINI_API_KEY=
GEMINI_MODEL=

OPENROUTER_API_KEY=
OPENROUTER_MODEL=

KODACLOUD_MODEL=

DISCORD_BOT_TOKEN=
DISCORD_ALLOWED_USERS=

TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USERS=

WHATSAPP_ALLOWED_NUMBERS=

X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_SECRET=

BLUESKY_HANDLE=
BLUESKY_APP_PASSWORD=
BLUESKY_ALLOWED_HANDLES=

GMAIL_USER=
GMAIL_APP_PASSWORD=

SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
"""

def initialize_moltyclaw():
    """Garante que toda a árvore de diretórios e arquivos base do MoltyClaw existam."""
    dirs = [
        MOLTY_DIR,
        os.path.join(MOLTY_DIR, "agents"),
        os.path.join(MOLTY_DIR, "skills"),
        os.path.join(MOLTY_DIR, "bundled", "skills"),
        os.path.join(MOLTY_DIR, "workspace"),
        os.path.join(MOLTY_DIR, "workspace", "skills"),
        os.path.join(MOLTY_DIR, "memory"),
        os.path.join(MOLTY_DIR, "canvas"),
        os.path.join(MOLTY_DIR, "logs"),
        os.path.join(MOLTY_DIR, "cron"),
        os.path.join(MOLTY_DIR, "mcp_modules"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        
    # Garante que o .env mestre exista com o template
    env_master = os.path.join(MOLTY_DIR, ".env")
    if not os.path.exists(env_master):
        with open(env_master, "w", encoding="utf-8") as f:
            f.write(DOTENV_TEMPLATE)
            
    # MIGRATION AUTOMÁTICA: Move arquivos velhos da raiz para o novo workspace (OpenClaw Parity)
    workspace_master = os.path.join(MOLTY_DIR, "workspace")
    legacy_files = ["SOUL.md", "IDENTITY.md", "USER.md", "MEMORY.md", "BOOTSTRAP.md", "TOOLS.md"]
    for lf in legacy_files:
        old_path = os.path.join(MOLTY_DIR, lf)
        new_path = os.path.join(workspace_master, lf)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                shutil.move(old_path, new_path)
            except: pass

    # Seed de skills nativas (se houver no pacote)
    bundled_target = os.path.join(MOLTY_DIR, "bundled", "skills")
    if not os.listdir(bundled_target):
        package_skills_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")
        if os.path.exists(package_skills_src) and os.path.isdir(package_skills_src):
            try:
                for item in os.listdir(package_skills_src):
                    s = os.path.join(package_skills_src, item)
                    d = os.path.join(bundled_target, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                    else:
                        shutil.copy2(s, d)
            except Exception:
                pass

    # Cria arquivos base se não existirem no workspace master (OpenClaw Parity)
    # BOOTSTRAP.md só deve ser criado em workspaces "zerados". 
    # Se SOUL.md ou IDENTITY.md já existem, assumimos que o ritual já foi feito.
    has_identity_files = os.path.exists(os.path.join(workspace_master, "SOUL.md")) or \
                         os.path.exists(os.path.join(workspace_master, "IDENTITY.md"))

    for filename, content in TEMPLATES.items():
        if filename == "BOOTSTRAP.md" and has_identity_files:
            continue # Não re-cria o bootstrap se já existe identidade
            
        path = os.path.join(workspace_master, filename)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    # 4. Garante que o moltyclaw.json central exista e tenha um token seguro
    config_path = os.path.join(MOLTY_DIR, "moltyclaw.json")
    if not os.path.exists(config_path):
        # Gera um token aleatório seguro (como o OpenClaw faz no onboard)
        new_token = secrets.token_hex(24)
        
        default_config = {
            "//": "==========================================",
            "//_1": "CONFIGURAÇÃO CENTRAL MOLTYCLAW",
            "//_2": "==========================================",
            "//_3": "Inspirado no OpenClaw, este arquivo centraliza segredos e configurações.",
            
            "providers": {
                "mistral": {"api_key": "${MISTRAL_API_KEY}", "model": "mistral-medium"},
                "gemini": {"api_key": "${GEMINI_API_KEY}", "model": "gemini-1.5-flash"},
                "openrouter": {"api_key": "${OPENROUTER_API_KEY}", "model": "google/gemini-2.0-flash"}
            },
            "channels": {
                "telegram": {"bot_token": "${TELEGRAM_BOT_TOKEN}"},
                "discord": {"bot_token": "${DISCORD_BOT_TOKEN}"}
            },
            "memory": {
                "strategy": "sqlite-vec",
                "path": "memory.db",
                "max_history_tokens": 4000
            },
            "gateway": {
                "auth": {
                    "token": new_token
                }
            }
        }
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
        except Exception:
            pass
