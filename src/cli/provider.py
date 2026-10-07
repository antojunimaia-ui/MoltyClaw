"""
MoltyClaw CLI — Provider & Model Selection
"""
import os
import sys
import re
import json
from . import console, MOLTY_DIR, Panel, Prompt, HAS_QUESTIONARY, MOLTY_STYLE, config_set

try:
    import questionary
except ImportError:
    questionary = None

try:
    from rich.table import Table
except ImportError:
    pass


def _fetch_kodacloud_models():
    """Busca a lista de modelos do Koda Cloud em tempo real via /v1/models."""
    import urllib.request
    try:
        req = urllib.request.Request("http://cn-01.hostzera.com.br:2137/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("models", [])
    except Exception as e:
        console.print(f"[dim yellow]Aviso: Koda Cloud inacessivel ({e}). Usando lista de fallback.[/dim yellow]")
        return [
            "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview",
            "mistral-small-2503", "codestral-2501", "devstral-medium-2507",
            "magistral-medium-2507", "meta-llama/llama-3.3-70b-instruct:free",
        ]


def _fetch_gemini_models(api_key: str):
    """Busca modelos disponíveis da API do Google Gemini em tempo real."""
    import urllib.request
    import urllib.error

    GEMINI_FALLBACK = [
        ("gemini-2.5-flash",         "Flash — Rápido e gratuito"),
        ("gemini-2.5-flash-lite",     "Flash Lite — Ultra rápido"),
        ("gemini-2.5-pro",            "Pro — Alta capacidade"),
        ("gemini-2.0-flash",          "Flash 2.0"),
        ("gemini-2.0-flash-lite",     "Flash Lite 2.0"),
    ]

    if not api_key:
        return GEMINI_FALLBACK

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}&pageSize=100"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())

        results = []
        for m in data.get("models", []):
            # Filtra somente modelos que suportam generateContent
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            model_id = m["name"].replace("models/", "")
            display = m.get("displayName", model_id)
            description = m.get("description", display)
            # Encurta descrições longas
            if len(description) > 50:
                description = description[:47] + "..."
            results.append((model_id, description))

        return results if results else GEMINI_FALLBACK

    except Exception as e:
        console.print(f"[dim yellow]Aviso: Nao foi possivel buscar modelos Gemini ({e}). Usando lista de fallback.[/dim yellow]")
        return GEMINI_FALLBACK


def _fetch_mistral_models(api_key: str):
    """Busca modelos disponíveis da API Mistral em tempo real."""
    MISTRAL_FALLBACK = [
        ("mistral-small-latest",  "Rápido e eficiente"),
        ("mistral-medium-latest", "Balanceado"),
        ("mistral-large-latest",  "Máxima capacidade"),
        ("pixtral-large-latest",  "Visão + Texto"),
        ("codestral-latest",      "Code generation"),
        ("mistral-embed",         "Embeddings"),
    ]
    if not api_key:
        return MISTRAL_FALLBACK
    import urllib.request, urllib.error
    try:
        req = urllib.request.Request(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "moltyclaw/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            if not mid:
                continue
            # mistral returns owned_by mistralai
            desc = m.get("description", "") or m.get("owned_by", "Mistral")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            results.append((mid, desc))
        return results if results else MISTRAL_FALLBACK
    except Exception as e:
        console.print(f"[dim yellow]Aviso: Nao foi possivel buscar modelos Mistral ({e}). Usando lista de fallback.[/dim yellow]")
        return MISTRAL_FALLBACK


def _fetch_openrouter_models():
    """Busca modelos disponíveis da API OpenRouter (pública, sem key)."""
    OPENROUTER_FALLBACK = [
        ("google/gemini-2.0-flash-exp:free",  "Gemini 2.0 (Grátis)"),
        ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B"),
        ("anthropic/claude-3.5-sonnet",       "Claude 3.5 Sonnet"),
        ("google/gemini-pro-1.5",             "Gemini Pro 1.5"),
        ("mistralai/mistral-large",           "Mistral Large"),
    ]
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "moltyclaw/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for m in data.get("data", [])[:60]:
            mid = m.get("id") or m.get("canonical_slug") or ""
            if not mid:
                continue
            name = m.get("name", mid)
            # use short name as description
            if len(name) > 50:
                name = name[:47] + "..."
            results.append((mid, name))
        return results if results else OPENROUTER_FALLBACK
    except Exception as e:
        console.print(f"[dim yellow]Aviso: Nao foi possivel buscar modelos OpenRouter ({e}). Usando lista de fallback.[/dim yellow]")
        return OPENROUTER_FALLBACK


def _fetch_opencode_models():
    """Busca modelos disponíveis da API OpenCode Zen."""
    OPENCODE_FALLBACK = [
        ("deepseek-v4-flash-free", "DeepSeek V4 Flash (Grátis)"),
        ("deepseek-v4-flash",      "DeepSeek V4 Flash"),
        ("deepseek-v4-pro",        "DeepSeek V4 Pro"),
        ("gpt-5.5",                "GPT-5.5"),
        ("gpt-5.6-luna",           "GPT-5.6 Luna"),
        ("claude-sonnet-5",        "Claude Sonnet 5"),
        ("gemini-3.5-flash",       "Gemini 3.5 Flash"),
    ]
    import urllib.request
    try:
        req = urllib.request.Request(
            "https://opencode.ai/zen/v1/models",
            headers={"User-Agent": "moltyclaw/1.0"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for m in data.get("data", []):
            mid = m.get("id", "")
            if not mid:
                continue
            owned = m.get("owned_by", "opencode")
            # description = owned + model id
            desc = f"{owned} — {mid}"
            if len(desc) > 50:
                desc = desc[:47] + "..."
            results.append((mid, desc))
        # sort to keep flash-free on top if present
        results.sort(key=lambda x: (0 if "free" in x[0] else 1, x[0]))
        return results if results else OPENCODE_FALLBACK
    except Exception as e:
        console.print(f"[dim yellow]Aviso: Nao foi possivel buscar modelos OpenCode ({e}). Usando lista de fallback.[/dim yellow]")
        return OPENCODE_FALLBACK


def _fetch_ollama_models():
    """Busca modelos instalados localmente no Ollama."""
    OLLAMA_FALLBACK = [
        ("llama3",    "Llama 3 8B"),
        ("llama3.1",  "Llama 3.1 8B"),
        ("mistral",   "Mistral 7B"),
        ("codellama", "Code Llama"),
        ("phi3",      "Phi-3 Mini"),
    ]
    import urllib.request
    # host configurable via OLLAMA_HOST
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        req = urllib.request.Request(f"{host.rstrip('/')}/api/tags", headers={"User-Agent": "moltyclaw/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
        results = []
        for m in data.get("models", []):
            mid = m.get("name", "").split(":")[0]
            if not mid:
                continue
            details = m.get("details", {})
            fam = details.get("family", "")
            desc = f"{fam} — {m.get('name','')}" if fam else m.get("name", mid)
            if len(desc) > 50:
                desc = desc[:47] + "..."
            results.append((mid, desc))
        return results if results else OLLAMA_FALLBACK
    except Exception:
        # silent fallback — Ollama often not running
        return OLLAMA_FALLBACK


def _read_env_key(env_path: str, key: str) -> str:
    """Lê o valor de uma chave do arquivo .env sem dependências externas."""
    if not os.path.exists(env_path):
        return ""
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    return ""


def cli_provider():
    """Gerencia o provider de IA (seleção e configuração)"""
    env_path = os.path.join(MOLTY_DIR, '.env')

    providers = {
        "mistral": {
            "name": "Mistral AI",
            "key": "MISTRAL_API_KEY",
            "url": "https://console.mistral.ai/",
            "models": ["mistral-small-latest", "mistral-medium-latest", "mistral-large-latest", "pixtral-large-latest"]
        },
        "gemini": {
            "name": "Google Gemini",
            "key": "GEMINI_API_KEY",
            "url": "https://aistudio.google.com/apikey",
            "models": ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro", "gemini-2.0-flash-exp"]
        },
        "openrouter": {
            "name": "OpenRouter",
            "key": "OPENROUTER_API_KEY",
            "url": "https://openrouter.ai/keys",
            "models": ["google/gemini-2.0-flash-exp:free", "meta-llama/llama-3.3-70b-instruct", "anthropic/claude-3.5-sonnet"]
        },
        "opencode": {
            "name": "OpenCode Zen",
            "key": "OPENCODE_ZEN_API_KEY",
            "url": "https://opencode.ai/auth",
            "models": ["deepseek-v4-flash-free", "deepseek-v4-flash", "gpt-5.5", "claude-sonnet-5", "gemini-3.5-flash"]
        },
        "kodacloud": {
            "name": "Koda Cloud",
            "key": None,
            "url": "http://cn-01.hostzera.com.br:2137",
            "models": _fetch_kodacloud_models()
        },
        "ollama": {
            "name": "Ollama (Local)",
            "key": None,
            "url": "https://ollama.com/",
            "models": ["llama3", "llama3.1", "mistral", "codellama", "phi3"]
        }
    }

    current_provider = None
    api_keys = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
            provider_match = re.search(r'MOLTY_PROVIDER=(.*)', content)
            if provider_match:
                current_provider = provider_match.group(1).strip()

            for p_id, p_info in providers.items():
                if p_info["key"]:
                    key_match = re.search(rf'{p_info["key"]}=(.*)', content)
                    if key_match:
                        key_value = key_match.group(1).strip()
                        api_keys[p_id] = "✅ Configurada" if key_value else "❌ Ausente"
                else:
                    api_keys[p_id] = "✅ Local"

    console.print(Panel.fit("[bold cyan]🤖 GERENCIADOR DE PROVIDERS[/bold cyan]"))

    table = Table(title="Providers Disponíveis", border_style="cyan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Nome", style="white")
    table.add_column("API Key", style="yellow")
    table.add_column("Status", style="green")

    for p_id, p_info in providers.items():
        status = "🟢 ATIVO" if p_id == current_provider else ""
        table.add_row(p_id, p_info["name"], api_keys.get(p_id, "❌ Ausente"), status)

    console.print(table)

    if current_provider:
        console.print(f"\n[bold green]Provider atual:[/bold green] {providers[current_provider]['name']} ({current_provider})")

    if HAS_QUESTIONARY:
        assert questionary is not None
        choices = [f"{p_id} - {p_info['name']}" for p_id, p_info in providers.items()]
        selection = questionary.select(
            "Selecione um provider:",
            choices=choices,
            style=MOLTY_STYLE,
        ).ask()

        if not selection:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)

        selected_id = selection.split(" - ")[0]
    else:
        console.print("\n[bold]Providers disponíveis:[/bold]")
        for i, (p_id, p_info) in enumerate(providers.items(), 1):
            console.print(f"  {i}. {p_id} - {p_info['name']}")

        choice = Prompt.ask("Selecione o número do provider", default="1")
        selected_id = list(providers.keys())[int(choice) - 1]

    selected_info = providers[selected_id]

    if selected_info["key"]:
        if api_keys.get(selected_id) != "✅ Configurada":
            console.print(f"\n[bold yellow]⚠ API Key não configurada para {selected_info['name']}[/bold yellow]")
            console.print(f"[dim]Obtenha sua chave em: {selected_info['url']}[/dim]")

            api_key = Prompt.ask(f"\nCole sua {selected_info['key']}")

            if api_key.strip():
                config_set(selected_info["key"], api_key.strip())
                console.print(f"[bold green]✅ API Key salva para {selected_info['name']}.[/bold green]")
            else:
                console.print("[bold yellow]⚠ Nenhuma chave informada. Chave não salva.[/bold yellow]")

    config_set("MOLTY_PROVIDER", selected_id)
    console.print(f"\n[bold green]✅ Provider alterado para: {selected_info['name']}[/bold green]")
    sys.exit(0)


def cli_model():
    """Gerencia o modelo de IA (seleção por provider)"""
    env_path = os.path.join(MOLTY_DIR, '.env')

    current_provider = "mistral"
    current_model = None

    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
            provider_match = re.search(r'MOLTY_PROVIDER=(.*)', content)
            if provider_match:
                current_provider = provider_match.group(1).strip()

            model_key = f"{current_provider.upper()}_MODEL" if current_provider != "opencode" else "OPENCODE_ZEN_MODEL"
            model_match = re.search(rf'{model_key}=(.*)', content)
            if model_match:
                current_model = model_match.group(1).strip()

    def _as_tuples(models):
        def _desc(m):
            return m.split("/")[-1].replace(":free", " (Free)").replace("-", " ").title()
        return [(m, _desc(m)) for m in models]

    # Feedback visual - fetch é síncrono e pode demorar 2-6s
    console.print(f"[dim]Buscando modelos para [cyan]{current_provider}[/cyan]...[/dim]")

    # Fetch lazy: só busca do provider atual (evita warnings de providers não usados)
    _provider_fetchers = {
        "mistral":    lambda: _fetch_mistral_models(_read_env_key(env_path, "MISTRAL_API_KEY")),
        "gemini":     lambda: _fetch_gemini_models(_read_env_key(env_path, "GEMINI_API_KEY")),
        "openrouter": lambda: _fetch_openrouter_models(),
        "opencode":   lambda: _fetch_opencode_models(),
        "kodacloud":  lambda: _as_tuples(_fetch_kodacloud_models()),
        "ollama":     lambda: _fetch_ollama_models(),
    }
    _provider_names = {
        "mistral": "Mistral AI",
        "gemini": "Google Gemini",
        "openrouter": "OpenRouter",
        "opencode": "OpenCode Zen",
        "kodacloud": "Koda Cloud",
        "ollama": "Ollama (Local)",
    }
    # Só executa fetch do provider atual
    _fetched_models = _provider_fetchers.get(current_provider, lambda: [])()
    models_by_provider = {
        current_provider: {
            "name": _provider_names.get(current_provider, current_provider.title()),
            "models": _fetched_models
        }
    }

    provider_info = models_by_provider.get(current_provider)
    if not provider_info:
        console.print(f"[bold red]❌ Provider '{current_provider}' não reconhecido[/bold red]")
        sys.exit(1)

    console.print(Panel.fit(
        f"[bold cyan]🧠 GERENCIADOR DE MODELOS[/bold cyan]\n"
        f"[dim]Provider atual:[/dim] [yellow]{provider_info['name']}[/yellow]"
    ))

    table = Table(title=f"Modelos disponíveis para {provider_info['name']}", border_style="cyan")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Modelo", style="white")
    table.add_column("Descrição", style="dim")
    table.add_column("Status", style="green")

    for idx, (model_id, description) in enumerate(provider_info["models"]):
        status = "🟢 ATIVO" if model_id == current_model else ""
        table.add_row(str(idx + 1), model_id, description, status)

    console.print(table)

    if current_model:
        console.print(f"\n[bold green]Modelo atual:[/bold green] {current_model}")

    if HAS_QUESTIONARY:
        assert questionary is not None
        choices = [f"{m[0]} - {m[1]}" for m in provider_info["models"]]
        selection = questionary.select(
            "Selecione um modelo:",
            choices=choices,
            style=MOLTY_STYLE,
        ).ask()

        if not selection:
            console.print("[dim]Operação cancelada.[/dim]")
            sys.exit(0)

        selected_model = selection.split(" - ")[0]
    else:
        console.print("\n[bold]Modelos disponíveis:[/bold]")
        for i, (model_id, desc) in enumerate(provider_info["models"], 1):
            console.print(f"  {i}. {model_id} - {desc}")

        choice = Prompt.ask("Selecione o número do modelo", default="1")
        selected_model = provider_info["models"][int(choice) - 1][0]

    model_key = f"{current_provider.upper()}_MODEL" if current_provider != "opencode" else "OPENCODE_ZEN_MODEL"
    config_set(model_key, selected_model)
    console.print(f"\n[bold green]✅ Modelo alterado para: {selected_model}[/bold green]")
    sys.exit(0)
