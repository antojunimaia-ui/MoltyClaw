import os
import sys
import json
import urllib.request
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from initializer import MOLTY_DIR
import re

console = Console()

try:
    import questionary
    HAS_QUESTIONARY = True
except ImportError:
    HAS_QUESTIONARY = False

def run_onboarding():
    console.print(Panel.fit("[bold red]Aviso de Segurança — por favor, leia.[/bold red]\n\n"
                            "O MoltyClaw é um projeto experimental. Espere encontrar arestas cortantes.\n"
                            "Este bot pode ler arquivos e executar ações localmente.\n"
                            "Um prompt malicioso pode enganá-lo a fazer coisas inseguras.\n\n"
                            "Se você não se sente confortável com segurança básica e controle de acesso, não rode o MoltyClaw.\n"
                            "Peça ajuda a alguém experiente antes de conectar integrações ou expor o agente à internet.\n\n"
                            "[bold yellow]Recomendações básicas:[/bold yellow]\n"
                            "- Use Whitelists e restrições de menção (Pairing/allowlists).\n"
                            "- Isole ferramentas críticas e dê o menor privilégio possível.\n"
                            "- Mantenha senhas e segredos fora do sistema de arquivos do agente.\n"
                            "- Use o modelo mais forte possível para bots com ferramentas ou caixas de entrada não-confiáveis.",
                            border_style="red"))
    
    if HAS_QUESTIONARY:
        confirm = questionary.confirm("Eu entendo que este sistema é poderoso e inerentemente arriscado. Continuar?", default=False).ask()
        if not confirm:
            console.print("[dim]Onboarding cancelado pelo usuário.[/dim]")
            sys.exit(0)
    else:
        confirm = Prompt.ask("Eu entendo que este sistema é poderoso e inerentemente arriscado. Continuar? [s/N]", default="N")
        if confirm.lower() not in ["s", "sim", "y", "yes"]:
            console.print("[dim]Onboarding cancelado pelo usuário.[/dim]")
            sys.exit(0)
            
    console.print("\n[bold cyan]🚀 Bem-vindo ao Assistente de Inicialização (Onboarding) do MoltyClaw![/bold cyan]\n")
    
    # 1. Provedor IA
    if HAS_QUESTIONARY:
        provider = questionary.select(
            "Qual provedor de IA servirá como cérebro principal?",
            choices=[
                questionary.Choice("Google Gemini (Recomendado)", value="gemini"),
                questionary.Choice("Mistral AI", value="mistral"),
                questionary.Choice("OpenRouter (Acesso a múltiplos modelos)", value="openrouter"),
                questionary.Choice("Ollama (Modelos Locais)", value="ollama")
            ]
        ).ask()
    else:
        console.print("1) Gemini (Recomendado)  2) Mistral  3) OpenRouter  4) Ollama")
        p = Prompt.ask("Selecione seu provedor", choices=["1", "2", "3", "4"], default="1")
        provider = "gemini" if p == "1" else "mistral" if p == "2" else "openrouter" if p == "3" else "ollama"
        
    # 2. API Key / Host
    if provider == "ollama":
        api_key = Prompt.ask("🌐 Host do Ollama", default="http://localhost:11434")
    else:
        api_key = Prompt.ask(f"🔑 Cole sua API Key para {provider.upper()}")
    
    # 2.5. Fetch Models e Escolha
    console.print(f"\n[dim]Conectando aos servidores ({provider.upper()}) para listar modelos compatíveis...[/dim]")
    models_list = []
    try:
        if provider == "gemini":
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                models_list = [m["name"].replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        elif provider == "mistral":
            req = urllib.request.Request("https://api.mistral.ai/v1/models")
            req.add_header("Authorization", f"Bearer {api_key}")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                models_list = [m["id"] for m in data.get("data", [])]
        elif provider == "openrouter":
            req = urllib.request.Request("https://openrouter.ai/api/v1/models")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                all_models = [m["id"] for m in data.get("data", [])]
                # No openrouter, filtramos para não exibir centenas de modelos
                models_list = [m for m in all_models if "free" in m.lower() or "gemini" in m.lower() or "claude" in m.lower()][:25]
                if not models_list: models_list = all_models[:25]
        elif provider == "ollama":
            # api_key aqui é o HOST
            req = urllib.request.Request(f"{api_key.rstrip('/')}/api/tags")
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                models_list = [m["name"] for m in data.get("models", [])]
    except Exception as e:
        console.print(f"[bold yellow]⚠ Falha na conexão com a API: {e}. Entrando com lista offline de fallback.[/bold yellow]")
        if provider == "gemini": models_list = ["gemini-2.0-flash", "gemini-2.5-pro"]
        elif provider == "mistral": models_list = ["mistral-large-latest", "pixtral-large-2411", "mistral-small-latest"]
        elif provider == "openrouter": models_list = ["google/gemini-2.0-flash-exp:free", "anthropic/claude-3-5-sonnet:beta"]
        elif provider == "ollama": models_list = ["llama3", "mistral", "phi3", "gemma"]
        
    if not models_list:
        models_list = ["default"]

    if HAS_QUESTIONARY:
        model_name = questionary.select(
            "🧠 Selecione o modelo padrão no qual o agente deve rodar:",
            choices=[questionary.Choice(m, value=m) for m in models_list]
        ).ask()
    else:
        for i, m in enumerate(models_list):
            console.print(f"{i+1}) {m}")
        idx = Prompt.ask("Selecione o número do modelo", default="1")
        try:
            model_name = models_list[int(idx)-1]
        except:
            model_name = models_list[0]
            
    # 3. Identidade
    agent_name = Prompt.ask("\n🤖 Qual será o nome da sua IA Mestra?", default="MoltyClaw")
    
    # 4. Integrações
    integrations_to_config = []
    if HAS_QUESTIONARY:
        integrations_to_config = questionary.checkbox(
            "🔌 Quais integrações você deseja configurar agora? (Espaço para marcar, Enter para confirmar)",
            choices=[
                questionary.Choice("Discord (Bot)", value="discord"),
                questionary.Choice("Telegram (Bot)", value="telegram"),
                questionary.Choice("WhatsApp (Beta)", value="whatsapp"),
                questionary.Choice("X (Twitter)", value="x"),
                questionary.Choice("Bluesky", value="bluesky"),
                questionary.Choice("Gmail (E-mail Automation)", value="gmail"),
                questionary.Choice("Spotify (Music Control)", value="spotify")
            ]
        ).ask() or []
    else:
        console.print("\nEscolha as integrações (ex: 1,2,5 ou deixe vazio):")
        console.print("1) Discord  2) Telegram  3) WhatsApp  4) X  5) Bluesky  6) Gmail  7) Spotify")
        choice = Prompt.ask("Sua escolha")
        mapping = {"1": "discord", "2": "telegram", "3": "whatsapp", "4": "x", "5": "bluesky", "6": "gmail", "7": "spotify"}
        for c in choice.split(","):
            if c.strip() in mapping:
                integrations_to_config.append(mapping[c.strip()])

    integration_secrets = {}
    for integration in integrations_to_config:
        console.print(f"\n[bold cyan]🛠️  Configurando {integration.upper()}:[/bold cyan]")
        
        if integration == "discord":
            integration_secrets["DISCORD_BOT_TOKEN"] = Prompt.ask("   🔑 Discord Bot Token")
            integration_secrets["DISCORD_ALLOWED_USERS"] = Prompt.ask("   👥 IDs de usuários permitidos (separados por vírgula, opcional)", default="")
            
        elif integration == "telegram":
            integration_secrets["TELEGRAM_BOT_TOKEN"] = Prompt.ask("   🔑 Telegram Bot Token (@BotFather)")
            integration_secrets["TELEGRAM_ALLOWED_USERS"] = Prompt.ask("   👥 IDs ou Usernames permitidos (separados por vírgula, opcional)", default="")
            
        elif integration == "whatsapp":
            integration_secrets["WHATSAPP_ALLOWED_NUMBERS"] = Prompt.ask("   📱 Números permitidos (ex: 5511999999999, opcional)", default="")
            
        elif integration == "x":
            integration_secrets["X_API_KEY"] = Prompt.ask("   🔑 X API Key")
            integration_secrets["X_API_SECRET"] = Prompt.ask("   🔑 X API Secret")
            integration_secrets["X_ACCESS_TOKEN"] = Prompt.ask("   🔑 X Access Token")
            integration_secrets["X_ACCESS_SECRET"] = Prompt.ask("   🔑 X Access Secret")
            
        elif integration == "bluesky":
            integration_secrets["BLUESKY_HANDLE"] = Prompt.ask("   🦋 Bluesky Handle (ex: seu.bsky.social)")
            integration_secrets["BLUESKY_APP_PASSWORD"] = Prompt.ask("   🔑 App Password (gerado nas configurações do Bsky)")
            integration_secrets["BLUESKY_ALLOWED_HANDLES"] = Prompt.ask("   👥 Handles permitidos (opcional)", default="")
            
        elif integration == "gmail":
            integration_secrets["GMAIL_USER"] = Prompt.ask("   📧 Seu Gmail")
            integration_secrets["GMAIL_APP_PASSWORD"] = Prompt.ask("   🔑 App Password do Google (16 caracteres)")
            
        elif integration == "spotify":
            integration_secrets["SPOTIFY_CLIENT_ID"] = Prompt.ask("   🆔 Spotify Client ID")
            integration_secrets["SPOTIFY_CLIENT_SECRET"] = Prompt.ask("   🔑 Spotify Client Secret")
            integration_secrets["SPOTIFY_REDIRECT_URI"] = Prompt.ask("   🔗 Redirect URI", default="http://localhost:8888/callback")

    console.print("\n[dim]🔧 Configurando Workspaces e Registros...[/dim]")
    env_path = os.path.join(MOLTY_DIR, '.env')
    
    # Mapeia chaves de provider baseado no template
    key_map_api = {
        "gemini": "GEMINI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "openrouter": "OPENROUTER_API_KEY"
    }
    key_map_model = {
        "gemini": "GEMINI_MODEL",
        "mistral": "MISTRAL_MODEL",
        "openrouter": "OPENROUTER_MODEL",
        "ollama": "OLLAMA_MODEL"
    }
    
    target_key_api = key_map_api.get(provider)
    target_key_model = key_map_model.get(provider)
    
    def update_dotenv_key(path, key, value):
        lines = []
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            # Tenta encontrar uma linha vazia que combine ou simplesmente apenda
            new_lines.append(f"{key}={value}\n")
            
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    # Atualiza as chaves no .env principal
    update_dotenv_key(env_path, "MOLTY_PROVIDER", provider)
    if provider == "ollama":
        update_dotenv_key(env_path, "OLLAMA_HOST", api_key)
    elif target_key_api:
        update_dotenv_key(env_path, target_key_api, api_key)
        
    if target_key_model:
        update_dotenv_key(env_path, target_key_model, model_name)
    
    # Salva os segredos das integrações selecionadas
    for k, v in integration_secrets.items():
        update_dotenv_key(env_path, k, v)
    
    console.print(f"\n[bold green]✅ Onboarding finalizado! {agent_name} está acoplado e pronto para a ação.[/bold green]")
    console.print("[cyan]Execute `moltyclaw` a qualquer momento em seu terminal para iniciar conversas interativas ou usar atalhos globais.[/cyan]")
    sys.exit(0)
