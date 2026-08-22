"""
MoltyClaw — Universal Slash Commands Engine (CLI & WebUI)
Fornece execução local e metadados para comandos rápidos:
/learn, /delegate, /skill, /mcp, /status, /model, /reset, /help
"""

import os
import sys
import json
import asyncio
from typing import Optional, Dict, Any, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from initializer import MOLTY_DIR
except ImportError:
    from src.initializer import MOLTY_DIR

SLASH_COMMANDS = [
    {
        "command": "/learn",
        "params": "<informação ou preferência>",
        "description": "Salva uma memória permanente ou fato no MEMORY.md do agente ativo.",
        "icon": "fa-solid fa-brain",
        "category": "Memória"
    },
    {
        "command": "/delegate",
        "params": "<agente> <tarefa>",
        "description": "Delega uma subtarefa em paralelo para outro agente especialista.",
        "icon": "fa-solid fa-people-arrows",
        "category": "Agentes"
    },
    {
        "command": "/skill",
        "params": "[nome_da_skill]",
        "description": "Lista todas as skills ativas ou consulta os manuais de uma skill específica.",
        "icon": "fa-solid fa-puzzle-piece",
        "category": "Skills"
    },
    {
        "command": "/mcp",
        "params": "[servidor]",
        "description": "Exibe o status dos servidores MCP conectados e lista de ferramentas.",
        "icon": "fa-solid fa-server",
        "category": "Ferramentas"
    },
    {
        "command": "/status",
        "params": "",
        "description": "Mostra o status de saúde do sistema, provedor, modelo e conectores.",
        "icon": "fa-solid fa-heart-pulse",
        "category": "Sistema"
    },
    {
        "command": "/model",
        "params": "[nome_do_modelo]",
        "description": "Verifica ou altera o modelo LLM do provedor atual.",
        "icon": "fa-solid fa-microchip",
        "category": "Modelo"
    },
    {
        "command": "/reset",
        "params": "",
        "description": "Limpa o histórico da conversa atual e reinicia o contexto.",
        "icon": "fa-solid fa-rotate-left",
        "category": "Conversa"
    },
    {
        "command": "/help",
        "params": "",
        "description": "Exibe o guia completo de comandos slash disponíveis.",
        "icon": "fa-solid fa-circle-question",
        "category": "Ajuda"
    }
]


def is_slash_command(text: str) -> bool:
    """Verifica se o texto de entrada do usuário é um comando slash."""
    if not text or not isinstance(text, str):
        return False
    clean = text.strip()
    return clean.startswith("/") and len(clean) > 1 and not clean.startswith("//")


async def handle_slash_command(text: str, agent=None, agent_id: str = "MoltyClaw") -> Dict[str, Any]:
    """
    Processa e executa um comando slash.
    Retorna um dicionário com:
    {
        "success": bool,
        "command": str,
        "reply": str, # Markdown para WebUI / Rich para CLI
        "action": Optional[str] # ex: 'clear_chat', 'reload_skills', etc.
    }
    """
    clean = text.strip()
    parts = clean.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    # ── /HELP ─────────────────────────────────────────────────────────────
    if cmd == "/help":
        lines = [
            "### 🧭 Catálogo de Comandos Slash do MoltyClaw\n",
            "| Comando | Parâmetros | Descrição |",
            "| :--- | :--- | :--- |"
        ]
        for sc in SLASH_COMMANDS:
            lines.append(f"| **`{sc['command']}`** | `{sc['params']}` | {sc['description']} |")
        lines.append("\n*Dica: Você pode digitar `/` no início de qualquer mensagem para autocompletar.*")
        return {
            "success": True,
            "command": "/help",
            "reply": "\n".join(lines)
        }

    # ── /LEARN ────────────────────────────────────────────────────────────
    if cmd == "/learn":
        if not args:
            return {
                "success": False,
                "command": "/learn",
                "reply": "⚠️ **Uso correto:** `/learn <fato ou instrução>`\n\n*Exemplo:* `/learn Eu prefiro respostas em TypeScript e uso o framework NestJS`"
            }

        # Resolve o diretório do agente
        if agent_id == "MoltyClaw":
            target_file = os.path.join(MOLTY_DIR, "workspace", "MEMORY.md")
            if not os.path.exists(target_file):
                target_file = os.path.join(MOLTY_DIR, "MEMORY.md")
        else:
            target_file = os.path.join(MOLTY_DIR, "agents", agent_id, "workspace", "MEMORY.md")
            os.makedirs(os.path.dirname(target_file), exist_ok=True)

        try:
            current_content = ""
            if os.path.exists(target_file):
                with open(target_file, "r", encoding="utf-8") as f:
                    current_content = f.read().strip()

            new_entry = f"- [Aprendizado]: {args}"
            if "## Fatos e Preferências do Usuário" in current_content:
                updated_content = current_content.replace(
                    "## Fatos e Preferências do Usuário",
                    f"## Fatos e Preferências do Usuário\n{new_entry}"
                )
            else:
                updated_content = f"{current_content}\n\n## Fatos e Preferências do Usuário\n{new_entry}".strip()

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return {
                "success": True,
                "command": "/learn",
                "reply": f"🧠 **Memória Permanente Atualizada com Sucesso!**\n\n> *\"{args}\"*\n\nGravado no arquivo `MEMORY.md` do agente `{agent_id}`."
            }
        except Exception as e:
            return {
                "success": False,
                "command": "/learn",
                "reply": f"❌ Erro ao gravar aprendizado na memória: {e}"
            }

    # ── /RESET /CLEAR ──────────────────────────────────────────────────────
    if cmd in ["/reset", "/clear"]:
        if agent and hasattr(agent, "conversation_history"):
            agent.conversation_history = []
        return {
            "success": True,
            "command": cmd,
            "action": "clear_chat",
            "reply": "🧹 **Histórico da conversa limpo com sucesso!** O contexto imediato foi resetado."
        }

    # ── /STATUS ────────────────────────────────────────────────────────────
    if cmd == "/status":
        from config_loader import get_config
        cfg = get_config()
        provider = os.getenv("MOLTY_PROVIDER", cfg.get("provider", "mistral"))
        model = cfg.get("model") or "Padrão do Provedor"
        browser_enabled = cfg.get("browser", {}).get("enabled", True)
        browser_mode = cfg.get("browser", {}).get("mode", "isolated")

        reply = f"""### 📊 Status do Sistema MoltyClaw
- **Agente Ativo:** `{agent_id}`
- **Provedor LLM:** `{provider.upper()}`
- **Modelo:** `{model}`
- **Navegador Web:** `{'✅ Ativado (' + browser_mode + ')' if browser_enabled else '❌ Desativado'}`
- **Diretório Raiz:** `{MOLTY_DIR}`
- **Status:** 🟢 Operacional e Pronto
"""
        return {
            "success": True,
            "command": "/status",
            "reply": reply
        }

    # ── /MODEL ────────────────────────────────────────────────────────────
    if cmd == "/model":
        from config_loader import get_config
        cfg = get_config()
        if not args:
            current = cfg.get("model") or "Padrão"
            return {
                "success": True,
                "command": "/model",
                "reply": f"🤖 **Modelo atual:** `{current}`\n\nPara alterar, digite: `/model <novo_modelo>` *(ex: `/model mistral-large-latest` ou `/model gpt-4o`)*"
            }

        config_path = os.path.join(MOLTY_DIR, "moltyclaw.json")
        cfg["model"] = args
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4)
            if agent:
                agent.model = args
            return {
                "success": True,
                "command": "/model",
                "reply": f"✅ **Modelo atualizado com sucesso para:** `{args}`"
            }
        except Exception as e:
            return {
                "success": False,
                "command": "/model",
                "reply": f"❌ Erro ao salvar novo modelo: {e}"
            }

    # ── /SKILL ────────────────────────────────────────────────────────────
    if cmd == "/skill":
        import skills
        all_skills = skills.load_skill_entries()

        if not args:
            if not all_skills:
                return {
                    "success": True,
                    "command": "/skill",
                    "reply": "📦 **Nenhuma skill instalada no momento.**\nVocê pode explorar e instalar habilidades na aba **Marketplace (ClawHub)** ou digitar `/skill <nome>`."
                }

            lines = ["### 🧩 Habilidades (Skills) Ativas do MoltyClaw\n"]
            for s in all_skills:
                status_badge = "✅ Pronto" if s.eligible else f"⚠️ Ausente: {s.eligibility_reason}"
                lines.append(f"- **{s.emoji} `{s.name}`** ({s.source}) — {status_badge}\n  *{s.description}*")
            lines.append("\n*Para ler detalhes de uma skill, use:* `/skill <nome_da_skill>`")
            return {
                "success": True,
                "command": "/skill",
                "reply": "\n".join(lines)
            }

        # Busca skill específica
        target_name = args.lower().replace("-", " ").strip()
        matched = next((s for s in all_skills if s.name.lower() == target_name or s.name.lower().replace("-", " ") == target_name), None)

        if matched:
            content = f"""### 🧩 Skill: {matched.emoji} {matched.name}
- **Origem:** `{matched.source}`
- **Status:** `{'Elegível e pronta' if matched.eligible else 'Requer dependências: ' + matched.eligibility_reason}`
- **Descrição:** {matched.description}
- **Requisitos:** Bins: `{matched.requires.get('bins', [])}` | Env: `{matched.requires.get('env', [])}`
"""
            return {
                "success": True,
                "command": "/skill",
                "reply": content
            }
        else:
            return {
                "success": False,
                "command": "/skill",
                "reply": f"❌ **Skill '{args}' não encontrada.** Digite `/skill` para ver a lista de habilidades instaladas."
            }

    # ── /MCP ──────────────────────────────────────────────────────────────
    if cmd == "/mcp":
        mcp_path = os.path.join(MOLTY_DIR, "mcp_servers.json")
        if not os.path.exists(mcp_path):
            return {
                "success": True,
                "command": "/mcp",
                "reply": "🔌 **Nenhum servidor MCP configurado no momento.**\nVocê pode adicionar servidores MCP na aba **MCP** do painel lateral."
            }

        try:
            with open(mcp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                servers = data.get("mcpServers", {})

            if not servers:
                return {
                    "success": True,
                    "command": "/mcp",
                    "reply": "🔌 **Nenhum servidor MCP ativo.**"
                }

            lines = ["### 🔌 Servidores MCP Configurados\n"]
            for s_name, s_conf in servers.items():
                cmd_str = s_conf.get("command", "")
                lines.append(f"- **`{s_name}`** (`{cmd_str}`)")
            return {
                "success": True,
                "command": "/mcp",
                "reply": "\n".join(lines)
            }
        except Exception as e:
            return {
                "success": False,
                "command": "/mcp",
                "reply": f"❌ Erro ao ler servidores MCP: {e}"
            }

    # ── /DELEGATE ─────────────────────────────────────────────────────────
    if cmd == "/delegate":
        if not args or len(args.split(maxsplit=1)) < 2:
            return {
                "success": False,
                "command": "/delegate",
                "reply": "⚠️ **Uso correto:** `/delegate <agente> <tarefa>`\n\n*Exemplo:* `/delegate Coder Crie uma função de validação de CPF em Python`"
            }

        target_sub, sub_task = args.split(maxsplit=1)
        target_sub = target_sub.lstrip("@").strip()

        # Verifica se o agente existe
        agents_dir = os.path.join(MOLTY_DIR, "agents")
        available = ["MoltyClaw"]
        if os.path.exists(agents_dir):
            for d in os.listdir(agents_dir):
                if os.path.isdir(os.path.join(agents_dir, d)):
                    available.append(d)

        matched_agent = next((a for a in available if a.lower() == target_sub.lower()), None)
        if not matched_agent:
            return {
                "success": False,
                "command": "/delegate",
                "reply": f"❌ **Agente '{target_sub}' não encontrado.** Agentes disponíveis: `{', '.join(available)}`"
            }

        if agent:
            # Executa com o agente delegado
            try:
                from moltyclaw import MoltyClaw
                sub_instance = MoltyClaw(agent_id=matched_agent) if matched_agent != "MoltyClaw" else agent
                reply_text = await sub_instance.ask(sub_task, silent=True)
                return {
                    "success": True,
                    "command": "/delegate",
                    "reply": f"🤖 **Resposta Delegada de [@{matched_agent}]:**\n\n{reply_text}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "command": "/delegate",
                    "reply": f"❌ Falha na execução delegada: {e}"
                }

        return {
            "success": True,
            "command": "/delegate",
            "reply": f"🚀 **Tarefa delegada para [@{matched_agent}]:**\n> *\"{sub_task}\"*"
        }

    return {
        "success": False,
        "command": cmd,
        "reply": f"❓ Comando desconhecido: `{cmd}`. Digite `/help` para ver os comandos disponíveis."
    }
