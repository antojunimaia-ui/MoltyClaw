import os
from dataclasses import dataclass
from typing import Any, Optional
from config_loader import get_config
from openai import AsyncOpenAI

try:
    from mistralai import Mistral
except ImportError:
    try:
        from mistralai.async_client import MistralAsyncClient as Mistral
    except ImportError:
        Mistral = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import ollama
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:
    ollama = None
    OllamaAsyncClient = None


@dataclass
class LLMClients:
    provider: str
    model: str
    api_key: Optional[str]
    mistral_client: Any = None
    openai_client: Any = None
    gemini_client: Any = None
    ollama_client: Any = None
    kodacloud_endpoint: Optional[str] = None


def resolve_provider_and_key(preferred_provider: str, agent_name: str = "MoltyClaw", console=None) -> tuple[str, Optional[str], dict]:
    molty_config = get_config()

    def get_key_for(prov):
        p_cfg = molty_config.get("providers", {}).get(prov, {})
        if prov == "mistral":
            return p_cfg.get("api_key") or os.getenv("MISTRAL_API_KEY")
        if prov == "gemini":
            return p_cfg.get("api_key") or os.getenv("GEMINI_API_KEY")
        if prov == "ollama":
            return "ollama"
        if prov == "kodacloud":
            return "kodacloud"
        if prov == "opencode":
            return p_cfg.get("api_key") or os.getenv("OPENCODE_ZEN_API_KEY")
        return p_cfg.get("api_key") or os.getenv("OPENROUTER_API_KEY")

    provider = preferred_provider
    api_key = get_key_for(provider)

    if not api_key:
        for fallback in ["kodacloud", "gemini", "mistral", "openrouter", "opencode", "ollama"]:
            if fallback == provider:
                continue
            fallback_key = get_key_for(fallback)
            if fallback_key:
                if console:
                    console.print(f"[dim]>> [{agent_name}] Provedor '{provider}' sem chave. Chave de '{fallback}' detectada. Alternando automaticamente...[/dim]")
                provider = fallback
                api_key = fallback_key
                break

    p_cfg = molty_config.get("providers", {}).get(provider, {})
    return provider, api_key, p_cfg


def resolve_model(provider: str, p_cfg: dict) -> str:
    if provider == "mistral":
        return os.getenv("MISTRAL_MODEL") or p_cfg.get("model") or "mistral-medium"
    elif provider == "gemini":
        return os.getenv("GEMINI_MODEL") or p_cfg.get("model") or "gemini-2.5-flash"
    elif provider == "ollama":
        return os.getenv("OLLAMA_MODEL") or p_cfg.get("model") or "llama3"
    elif provider == "kodacloud":
        return os.getenv("KODACLOUD_MODEL") or p_cfg.get("model") or "gemini-2.5-flash"
    elif provider == "opencode":
        return os.getenv("OPENCODE_ZEN_MODEL") or p_cfg.get("model") or "deepseek-v4-flash-free"
    else:
        return os.getenv("OPENROUTER_MODEL") or p_cfg.get("model") or "google/gemini-2.0-flash"


def initialize_clients(
    provider: str,
    model: str,
    api_key: Optional[str],
    system_instruction: Optional[str] = None,
    agent_name: str = "MoltyClaw",
    console=None
) -> LLMClients:
    clients = LLMClients(provider=provider, model=model, api_key=api_key)

    if not api_key:
        _key_env = {
            "mistral": "MISTRAL_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "opencode": "OPENCODE_ZEN_API_KEY",
        }.get(provider, "OPENROUTER_API_KEY")
        if console:
            console.print(f"[{agent_name}] [warning]Aviso: Chave de API para provedor {provider} não encontrada ({_key_env}).[/warning]")
        return clients

    if provider == "mistral":
        try:
            from mistralai import Mistral
            clients.mistral_client = Mistral(api_key=api_key)
        except (ImportError, TypeError):
            from mistralai.async_client import MistralAsyncClient
            clients.mistral_client = MistralAsyncClient(api_key=api_key)

    elif provider == "gemini":
        if genai:
            genai.configure(api_key=api_key)
            clients.gemini_client = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction
            )

    elif provider == "ollama":
        if OllamaAsyncClient:
            clients.ollama_client = OllamaAsyncClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))

    elif provider == "kodacloud":
        clients.openai_client = AsyncOpenAI(
            base_url="http://cn-01.hostzera.com.br:2137/v1",
            api_key="not-needed",
        )
        clients.kodacloud_endpoint = "http://cn-01.hostzera.com.br:2137/v1/chat"

    elif provider == "opencode":
        clients.openai_client = AsyncOpenAI(
            base_url="https://opencode.ai/zen/v1",
            api_key=api_key,
        )

    else:
        clients.openai_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    return clients