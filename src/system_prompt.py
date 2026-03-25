"""
MoltyClaw — Dynamic System Prompt Builder
Inspirado no system-prompt.ts do OpenClaw.

Monta o system prompt de forma modular e injeta metadados de runtime
para que o modelo saiba exatamente onde está rodando e com quais capacidades.
"""
import os
import platform
import sys
from typing import Optional

# ── Constantes ────────────────────────────────────────────────────────────────

VERSION = "26.24.3"
SILENT_TOKEN = "NO_REPLY"
TOOL_FORMAT_EXAMPLE = '<tool>\n{"action": "GOTO", "param": "https://site.com"}\n</tool>'

# ──────────────────────────────────────────────────────────────────────────────
# Seções individuais (retornam listas de strings, filtradas e juntadas no final)
# ──────────────────────────────────────────────────────────────────────────────

def _build_identity(name: str, identity_file_content: str = "") -> list[str]:
    identity = identity_file_content.strip() if identity_file_content else ""
    return [
        f"Você é o {name}, um agente autônomo pessoal rodando dentro do MoltyClaw v{VERSION}.",
        identity,
        ""
    ] if identity else [
        f"Você é o {name}, um agente autônomo pessoal rodando dentro do MoltyClaw v{VERSION}.",
        ""
    ]


def _build_user_section(user_content: str) -> list[str]:
    user = user_content.strip()
    if not user:
        return []
    return ["## Sobre Seu Usuário", user, ""]


def _build_bootstrap_section(bootstrap_content: str) -> list[str]:
    bootstrap = bootstrap_content.strip()
    if not bootstrap:
        return []
    return [
        "## ⚠️ INSTRUÇÕES DE INICIALIZAÇÃO (BOOTSTRAP)",
        "Você encontrou um arquivo BOOTSTRAP.md no seu diretório. Siga as instruções abaixo IMEDIATAMENTE:",
        bootstrap,
        "",
        "IMPORTANTE: Não delete este arquivo até que você tenha definido sua IDENTIDADE e o PERFIL DO USUÁRIO com sucesso.",
        ""
    ]


def _build_soul_section(soul_content: str) -> list[str]:
    soul = soul_content.strip()
    if not soul:
        return []
    return ["## Identidade e Alma", soul, ""]


def _build_tool_format_section(is_minimal: bool) -> list[str]:
    if is_minimal:
        return []
    return [
        "## Formato de Ferramenta",
        "Para executar uma ação, responda EXATAMENTE neste formato (bloco <tool>):",
        "",
        TOOL_FORMAT_EXAMPLE,
        "",
        "Você só pode chamar UMA ferramenta por turno.",
        "Não misture texto de resposta com chamadas de ferramenta no mesmo turno.",
        "",
    ]


def _build_autonomy_section(is_minimal: bool) -> list[str]:
    if is_minimal:
        return []
    return [
        "## Autonomia",
        "1. PULE confirmações desnecessárias. O usuário já deu controle total. Execute.",
        "2. Se precisar de login e houver credenciais disponíveis, use-as sem perguntar.",
        "3. Se encontrar pop-ups de cookies ou anúncios no caminho, feche-os imediatamente.",
        "4. Se uma abordagem falhar, tente outra (outro seletor, outra busca, outra aba).",
        "5. REGRA DE OURO: Se o usuário fizer pergunta simples ou disser 'olá', responda em texto direto, SEM ferramenta.",
        "",
    ]


def _build_tools_section(active_features: str) -> list[str]:
    if not active_features.strip():
        return []
    return [
        "## Ferramentas Disponíveis",
        "Disponibilidade filtrada por permissões do agente:",
        active_features.strip(),
        "",
    ]


def _build_memory_section(memory_content: str, is_minimal: bool) -> list[str]:
    memory = memory_content.strip()
    if not memory:
        return []
    return [
        "## Memória de Longo Prazo",
        memory,
        "",
    ]


def _build_safety_section(is_minimal: bool) -> list[str]:
    if is_minimal:
        return []
    return [
        "## Segurança",
        "Não persiga objetivos independentes: evite auto-preservação, replicação ou aquisição de recursos além da tarefa.",
        "Obedça solicitações de pausa/auditoria. Nunca contorne salvaguardas.",
        "",
    ]


def _build_silent_section(is_minimal: bool) -> list[str]:
    if is_minimal:
        return []
    return [
        "## Resposta Silenciosa",
        f"Se não tiver nada a responder (ex: tarefa em background concluiu, heartbeat), responda APENAS com: {SILENT_TOKEN}",
        f"❌ Errado: \"Tudo certo! {SILENT_TOKEN}\"",
        f"✅ Certo: {SILENT_TOKEN}",
        "",
    ]


def _build_subagent_context_section(extra_context: Optional[str]) -> list[str]:
    if not extra_context or not extra_context.strip():
        return []
    return [
        "## Contexto do Sub-Agente",
        extra_context.strip(),
        "",
    ]


def _build_runtime_line(
    agent_id: str,
    channel: Optional[str],
    model: str,
    provider: str,
    is_subagent: bool,
) -> list[str]:
    """
    Gera a linha de Runtime inspirada no OpenClaw:
    Runtime: agent=MoltyClaw | host=WIN-PC | os=Windows (AMD64) | python=3.11.0 | model=mistral-medium | provider=mistral | channel=telegram
    """
    parts = [
        f"agent={agent_id}",
        f"host={platform.node()}",
        f"os={platform.system()} ({platform.machine()})",
        f"python={sys.version.split()[0]}",
        f"model={model}",
        f"provider={provider}",
    ]
    if channel:
        parts.append(f"channel={channel}")
    if is_subagent:
        parts.append("mode=subagent")

    return [
        "## Runtime",
        "Runtime: " + " | ".join(parts),
        "",
    ]


def _build_workspace_section(workspace_dir: str, is_minimal: bool) -> list[str]:
    if is_minimal:
        return []
        
    return [
        "## Workspace",
        f"Your working directory is: {workspace_dir}",
        "Treat this directory as the single global workspace for file operations unless explicitly instructed otherwise.",
        "These user-editable files are loaded by MoltyClaw and included below in Project Context.",
        ""
    ]

def _build_project_context_header(has_files: bool) -> list[str]:
    if not has_files:
        return []
    return ["# Project Context", ""]


# ──────────────────────────────────────────────────────────────────────────────
# Builder principal
# ──────────────────────────────────────────────────────────────────────────────

def build_system_prompt(
    name: str,
    agent_id: str,
    model: str,
    provider: str,
    workspace_dir: str = "",
    soul_content: str = "",
    identity_content: str = "",
    user_content: str = "",
    bootstrap_content: str = "",
    memory_content: str = "",
    active_features: str = "",
    mcp_placeholder: str = "",
    channel: Optional[str] = None,
    is_subagent: bool = False,
    extra_context: Optional[str] = None,
) -> str:
    """
    Constrói o system prompt de forma modular.

    Modos:
      - is_subagent=False  → prompt completo (Master / WebUI)
      - is_subagent=True   → prompt minimal (sub-agentes recebem versão reduzida)
    """
    is_minimal = is_subagent
    has_files = any([soul_content, identity_content, user_content, bootstrap_content, memory_content])

    sections: list[list[str]] = [
        _build_identity(name, identity_content),
        _build_workspace_section(workspace_dir, is_minimal),
        _build_project_context_header(has_files),
        _build_soul_section(soul_content),
        _build_user_section(user_content),
        _build_bootstrap_section(bootstrap_content),
        _build_autonomy_section(is_minimal),
        _build_tool_format_section(is_minimal),
        _build_tools_section(active_features),
        _build_memory_section(memory_content, is_minimal),
        _build_safety_section(is_minimal),
        _build_subagent_context_section(extra_context if is_minimal else None),
        _build_silent_section(is_minimal),
        _build_runtime_line(agent_id, channel, model, provider, is_subagent),
    ]

    lines: list[str] = []
    for section in sections:
        lines.extend(section)

    # Injeta placeholder do MCP no final (será substituído depois pelo MCPHub)
    if mcp_placeholder:
        lines.append(mcp_placeholder)

    return "\n".join(lines)
