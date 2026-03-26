"""
MoltyClaw — Skills System
Inspirado no sistema de Skills do OpenClaw.

Skills são pacotes modulares que estendem as capacidades do agente com
conhecimento especializado, workflows e ferramentas reutilizáveis.

Arquitetura de Progressive Disclosure:
  Nível 1 — Metadata (name + description): sempre no system prompt (~100 tokens/skill)
  Nível 2 — Body (SKILL.md completo): carregado sob demanda via tool SKILL_USE
  Nível 3 — Scripts/References/Assets: executados/lidos pelo agente quando necessário
"""

import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from typing import Optional

# ── Constantes ────────────────────────────────────────────────────────────────

MOLTY_DIR = os.path.join(os.path.expanduser("~"), ".moltyclaw")

# Diretórios de skills por fonte (precedência: bundled < managed < workspace)
BUNDLED_SKILLS_DIR = os.path.join(MOLTY_DIR, "bundled", "skills")
MANAGED_SKILLS_DIR = os.path.join(MOLTY_DIR, "skills")
WORKSPACE_SKILLS_DIR = os.path.join(MOLTY_DIR, "workspace", "skills")

# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class SkillEntry:
    """Representação de uma skill carregada."""
    name: str
    description: str
    emoji: str
    skill_dir: str
    skill_md_path: str
    source: str               # "bundled" | "managed" | "workspace"
    requires: dict = field(default_factory=dict)
    eligible: bool = True
    eligibility_reason: str = ""


# ── Parser de YAML Frontmatter ────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n",
    re.DOTALL,
)


def _parse_frontmatter(content: str) -> dict:
    """
    Parseia o YAML frontmatter de um SKILL.md.
    Usa yaml.safe_load se disponível, senão faz parsing manual simples.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    raw_yaml = match.group(1)

    # Tenta usar PyYAML se instalado
    try:
        import yaml
        return yaml.safe_load(raw_yaml) or {}
    except ImportError:
        pass

    # Fallback: parsing manual de chaves simples (key: value)
    result = {}
    current_key = None
    for line in raw_yaml.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Detecta key: value
        if ":" in stripped and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            # Remove aspas
            if val and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]

            # Tenta parsear listas inline [a, b, c]
            if val.startswith("[") and val.endswith("]"):
                items = val[1:-1].split(",")
                val = [item.strip().strip("'\"") for item in items if item.strip()]

            result[key] = val
            current_key = key

        # Detecta itens de lista (- value)
        elif stripped.startswith("-") and current_key:
            item = stripped[1:].strip().strip("'\"")
            if not isinstance(result.get(current_key), list):
                result[current_key] = []
            result[current_key].append(item)

    return result


def _extract_body(content: str) -> str:
    """Extrai o body do SKILL.md (tudo depois do frontmatter)."""
    match = _FRONTMATTER_RE.match(content)
    if match:
        return content[match.end():]
    return content


# ── Verificação de Elegibilidade ──────────────────────────────────────────────

def _check_eligibility(requires: dict) -> tuple[bool, str]:
    """
    Verifica se os requisitos de uma skill são atendidos no ambiente atual.

    Retorna (eligible, reason).
    """
    if not requires:
        return True, ""

    # Verifica binários no PATH
    bins = requires.get("bins", [])
    if isinstance(bins, str):
        bins = [bins]
    for binary in bins:
        if not shutil.which(binary):
            return False, f"binário '{binary}' não encontrado no PATH"

    # Verifica variáveis de ambiente
    env_vars = requires.get("env", [])
    if isinstance(env_vars, str):
        env_vars = [env_vars]
    for var in env_vars:
        if not os.getenv(var):
            return False, f"variável de ambiente '{var}' não definida"

    return True, ""


# ── Loader Principal ──────────────────────────────────────────────────────────

def _scan_skills_dir(directory: str, source: str) -> list[SkillEntry]:
    """
    Escaneia um diretório de skills e retorna lista de SkillEntry.
    Cada subpasta que contenha um SKILL.md é considerada uma skill.
    """
    entries = []

    if not os.path.isdir(directory):
        return entries

    for item in sorted(os.listdir(directory)):
        skill_dir = os.path.join(directory, item)
        skill_md = os.path.join(skill_dir, "SKILL.md")

        if not os.path.isdir(skill_dir) or not os.path.isfile(skill_md):
            continue

        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        frontmatter = _parse_frontmatter(content)

        name = frontmatter.get("name", item)
        description = frontmatter.get("description", "")
        emoji = frontmatter.get("emoji", "🧩")
        requires = frontmatter.get("requires", {})

        # Suporta metadata aninhada estilo OpenClaw
        if "metadata" in frontmatter:
            meta = frontmatter["metadata"]
            if isinstance(meta, dict):
                oc_meta = meta.get("openclaw", meta.get("moltyclaw", {}))
                if isinstance(oc_meta, dict):
                    emoji = oc_meta.get("emoji", emoji)
                    requires = oc_meta.get("requires", requires)

        if isinstance(requires, str):
            requires = {}

        eligible, reason = _check_eligibility(requires)

        entries.append(SkillEntry(
            name=name,
            description=description,
            emoji=emoji,
            skill_dir=skill_dir,
            skill_md_path=skill_md,
            source=source,
            requires=requires,
            eligible=eligible,
            eligibility_reason=reason,
        ))

    return entries


def load_skill_entries(workspace_dir: str = "") -> list[SkillEntry]:
    """
    Carrega todas as skills dos 3 diretórios com merge por precedência.

    Precedência (menor → maior): bundled < managed < workspace
    Skills com mesmo name são sobrescritas pela fonte de maior precedência.
    """
    merged: dict[str, SkillEntry] = {}

    # 1. Bundled (menor precedência)
    for entry in _scan_skills_dir(BUNDLED_SKILLS_DIR, "bundled"):
        merged[entry.name] = entry

    # 2. Managed
    for entry in _scan_skills_dir(MANAGED_SKILLS_DIR, "managed"):
        merged[entry.name] = entry

    # 3. Workspace (maior precedência)
    ws_skills_dir = workspace_dir if workspace_dir else WORKSPACE_SKILLS_DIR
    if ws_skills_dir != WORKSPACE_SKILLS_DIR:
        ws_skills_dir = os.path.join(ws_skills_dir, "skills")
    for entry in _scan_skills_dir(ws_skills_dir, "workspace"):
        merged[entry.name] = entry

    return list(merged.values())


def filter_eligible_skills(entries: list[SkillEntry]) -> list[SkillEntry]:
    """Retorna apenas skills cujos requisitos são atendidos."""
    return [e for e in entries if e.eligible]


# ── Geração de Prompt ─────────────────────────────────────────────────────────

def build_skills_metadata_prompt(entries: list[SkillEntry]) -> str:
    """
    Gera o bloco de metadata das skills para injeção no system prompt.
    Contém apenas name + description (Progressive Disclosure nível 1).

    Este texto fica SEMPRE no system prompt para o LLM saber quais skills existem.
    """
    eligible = filter_eligible_skills(entries)
    if not eligible:
        return ""

    lines = [
        "## Skills Disponíveis",
        "As seguintes skills estão carregadas. Para ativar uma skill e carregar",
        "suas instruções completas, use a ferramenta SKILL_USE com o nome da skill.",
        "",
    ]

    for entry in eligible:
        lines.append(f"- {entry.emoji} **{entry.name}** — {entry.description}")

    lines.append("")
    return "\n".join(lines)


# ── Carregamento do Body (sob demanda) ────────────────────────────────────────

def load_skill_body(entry: SkillEntry) -> str:
    """
    Carrega o body completo do SKILL.md de uma skill (Progressive Disclosure nível 2).
    Chamado quando o agente ativa a skill via tool SKILL_USE.
    """
    try:
        with open(entry.skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return f"Erro: Não foi possível ler o SKILL.md de '{entry.name}'."

    body = _extract_body(content).strip()
    if not body:
        return f"A skill '{entry.name}' não possui instruções detalhadas no body do SKILL.md."

    return body


def find_skill_by_name(entries: list[SkillEntry], name: str) -> Optional[SkillEntry]:
    """Busca uma skill pelo nome (case-insensitive)."""
    name_lower = name.lower().strip()
    for entry in entries:
        if entry.name.lower() == name_lower:
            return entry
    return None


# ── Instalação / Desinstalação ────────────────────────────────────────────────

def install_skill(source_path: str) -> tuple[bool, str]:
    """
    Instala uma skill no diretório managed (~/.moltyclaw/skills/).

    Aceita:
      - Caminho para uma pasta contendo SKILL.md
      - Caminho para um arquivo .skill (zip)

    Retorna (sucesso, mensagem).
    """
    os.makedirs(MANAGED_SKILLS_DIR, exist_ok=True)

    # Caso 1: arquivo .skill (zip)
    if source_path.endswith(".skill") and os.path.isfile(source_path):
        try:
            with zipfile.ZipFile(source_path, "r") as zf:
                # Verifica se contém SKILL.md
                names = zf.namelist()
                has_skill_md = any(
                    n.endswith("SKILL.md") and n.count("/") <= 1
                    for n in names
                )
                if not has_skill_md:
                    return False, "Arquivo .skill inválido: não contém SKILL.md"

                # Detecta o nome da skill pelo diretório raiz do zip
                root_dirs = set()
                for n in names:
                    parts = n.split("/")
                    if len(parts) > 1 and parts[0]:
                        root_dirs.add(parts[0])

                if len(root_dirs) == 1:
                    skill_name = root_dirs.pop()
                    dest = os.path.join(MANAGED_SKILLS_DIR, skill_name)
                    zf.extractall(MANAGED_SKILLS_DIR)
                else:
                    # Zip flat (sem pasta raiz) — usa nome do arquivo
                    skill_name = os.path.splitext(os.path.basename(source_path))[0]
                    dest = os.path.join(MANAGED_SKILLS_DIR, skill_name)
                    os.makedirs(dest, exist_ok=True)
                    zf.extractall(dest)

                return True, f"Skill '{skill_name}' instalada em {dest}"

        except zipfile.BadZipFile:
            return False, "Arquivo .skill corrompido (não é um zip válido)"

    # Caso 2: pasta local
    if os.path.isdir(source_path):
        skill_md = os.path.join(source_path, "SKILL.md")
        if not os.path.isfile(skill_md):
            return False, f"Pasta '{source_path}' não contém SKILL.md"

        skill_name = os.path.basename(source_path.rstrip("/\\"))
        dest = os.path.join(MANAGED_SKILLS_DIR, skill_name)

        if os.path.exists(dest):
            shutil.rmtree(dest)

        shutil.copytree(source_path, dest)
        return True, f"Skill '{skill_name}' instalada em {dest}"

    return False, f"Caminho inválido: '{source_path}'"


def uninstall_skill(name: str) -> tuple[bool, str]:
    """
    Remove uma skill do diretório managed.
    Retorna (sucesso, mensagem).
    """
    skill_dir = os.path.join(MANAGED_SKILLS_DIR, name)

    if not os.path.isdir(skill_dir):
        return False, f"Skill '{name}' não encontrada em {MANAGED_SKILLS_DIR}"

    shutil.rmtree(skill_dir)
    return True, f"Skill '{name}' desinstalada com sucesso"


# ── Scaffold de Nova Skill ────────────────────────────────────────────────────

def create_skill_scaffold(
    name: str,
    target_dir: str = "",
    resources: Optional[list[str]] = None,
) -> tuple[bool, str]:
    """
    Gera o scaffold de uma nova skill com SKILL.md template.

    Args:
        name: Nome da skill (ex: "my-skill")
        target_dir: Diretório onde criar (default: workspace skills)
        resources: Lista de subpastas a criar ("scripts", "references", "assets")

    Retorna (sucesso, caminho_criado).
    """
    if not target_dir:
        target_dir = WORKSPACE_SKILLS_DIR

    skill_dir = os.path.join(target_dir, name)

    if os.path.exists(skill_dir):
        return False, f"Skill '{name}' já existe em {skill_dir}"

    os.makedirs(skill_dir, exist_ok=True)

    # Cria subpastas de recursos
    if resources:
        for res in resources:
            if res in ("scripts", "references", "assets"):
                os.makedirs(os.path.join(skill_dir, res), exist_ok=True)

    # Gera SKILL.md template
    template = f"""---
name: {name}
description: TODO — Descreva o que esta skill faz e quando deve ser usada.
emoji: 🧩
requires:
  bins: []
  env: []
---

# {name.replace('-', ' ').title()}

TODO — Escreva as instruções detalhadas da skill aqui.

## Como usar

Descreva o workflow passo a passo.

## Exemplos

Adicione exemplos de uso.
"""

    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(template)

    return True, skill_dir


# ── Package (empacotamento) ───────────────────────────────────────────────────

def package_skill(skill_dir: str, output_dir: str = "") -> tuple[bool, str]:
    """
    Empacota uma skill em um arquivo .skill (zip) para distribuição.

    Retorna (sucesso, caminho_do_arquivo).
    """
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return False, f"'{skill_dir}' não contém SKILL.md"

    skill_name = os.path.basename(skill_dir.rstrip("/\\"))

    if not output_dir:
        output_dir = os.path.dirname(skill_dir) or "."

    output_path = os.path.join(output_dir, f"{skill_name}.skill")

    try:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(skill_dir):
                for file in files:
                    abs_path = os.path.join(root, file)
                    arc_name = os.path.join(
                        skill_name,
                        os.path.relpath(abs_path, skill_dir),
                    )
                    zf.write(abs_path, arc_name)

        return True, output_path

    except Exception as e:
        return False, f"Erro ao empacotar: {e}"
