import os
import sys
import json
import urllib.request
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

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
                questionary.Choice("Gemini 2.0 Flash (Recomendado)", value="gemini"),
                questionary.Choice("Mistral AI", value="mistral"),
                questionary.Choice("OpenRouter (Acesso a múltiplos modelos)", value="openrouter")
            ]
        ).ask()
    else:
        console.print("1) Gemini (Recomendado)  2) Mistral  3) OpenRouter")
        p = Prompt.ask("Selecione seu provedor", choices=["1", "2", "3"], default="1")
        provider = "gemini" if p == "1" else "mistral" if p == "2" else "openrouter"
        
    # 2. API Key
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
    except Exception as e:
        console.print(f"[bold yellow]⚠ Falha na conexão com a API: {e}. Entrando com lista offline de fallback.[/bold yellow]")
        if provider == "gemini": models_list = ["gemini-2.0-flash", "gemini-2.5-pro"]
        elif provider == "mistral": models_list = ["mistral-large-latest", "pixtral-large-2411", "mistral-small-latest"]
        elif provider == "openrouter": models_list = ["google/gemini-2.0-flash-exp:free", "anthropic/claude-3-5-sonnet:beta"]
        
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
    
    console.print("\n[dim]🔧 Configurando Workspaces e Registros...[/dim]")
    env_path = os.path.join(os.getcwd(), '.env')
    
    key_map = {
        "gemini": "GEMINI_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "openrouter": "OPENROUTER_API_KEY"
    }
    target_key = key_map[provider]
    
    # Edita/Cria o .env
    lines = []
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
    # Remove vars de provider conflitantes
    new_lines = []
    for line in lines:
        if not line.startswith("MOLTY_PROVIDER=") and not line.startswith(f"{target_key}=") and not line.startswith("MOLTY_MODEL="):
            new_lines.append(line)
            
    new_lines.append(f"MOLTY_PROVIDER={provider}\n")
    new_lines.append(f"MOLTY_MODEL={model_name}\n")
    new_lines.append(f"{target_key}={api_key}\n")
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    # Scaffold do Workspace Mestre
    base_dir = os.path.join(os.path.expanduser("~"), ".moltyclaw")
    os.makedirs(base_dir, exist_ok=True)
    memory_path = os.path.join(base_dir, "MEMORY.md")
    soul_path = os.path.join(base_dir, "SOUL.md")
    
    if not os.path.exists(memory_path):
        with open(memory_path, 'w', encoding='utf-8') as f:
            f.write(f"# MEMORY\n\nMemória episódica de longo prazo ativada para {agent_name} no Onboarding.\n")
    if not os.path.exists(soul_path):
        with open(soul_path, 'w', encoding='utf-8') as f:
            f.write(f"# SOUL.md - Identidade\n\nVocê é {agent_name}, um agente autônomo conectado ao MoltyClaw.\nVocê ajuda o usuário de forma direta e sem ser prolixo.\n")
            
    console.print(f"\n[bold green]✅ Onboarding finalizado! {agent_name} está acoplado e pronto para a ação.[/bold green]")
    console.print("[cyan]Execute `moltyclaw` a qualquer momento em seu terminal para iniciar conversas interativas ou usar atalhos globais.[/cyan]")
    sys.exit(0)
