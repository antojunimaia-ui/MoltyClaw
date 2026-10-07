"""Agent display name + ANSI Shadow banner (shared by Flask WebUI and FastAPI Gateway)."""
import os
import re
import unicodedata

try:
    from initializer import MOLTY_DIR
except ImportError:
    from src.initializer import MOLTY_DIR


def _read_identity_file(agent_id: str) -> str:
    base = MOLTY_DIR if agent_id == "MoltyClaw" else os.path.join(MOLTY_DIR, "agents", agent_id)
    path = os.path.join(base, "workspace", "IDENTITY.md")
    if not os.path.exists(path):
        old = os.path.join(base, "IDENTITY.md")
        if os.path.exists(old):
            path = old
        elif agent_id == "MoltyClaw":
            for alt in ("IDENTITY.md", os.path.join(os.getcwd(), "IDENTITY.md")):
                if os.path.exists(alt):
                    path = alt
                    break
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    return ""


def resolve_display_name(agent_id: str = "MoltyClaw") -> str:
    """Extrai `- **Nome**: X` do IDENTITY.md, com fallbacks."""
    content = _read_identity_file(agent_id)
    if content:
        m = re.search(r"\*\*\s*Nome\s*\*\*\s*:\s*(.+)", content, re.IGNORECASE)
        if m:
            raw = m.group(1).strip().strip("*_`\"'").split("\n")[0].strip()
            # Remove prefixos tipo "- " que sobram do markdown
            raw = re.sub(r"^[\-\*\s]+", "", raw).strip()
            if raw and raw.lower() not in ("", "a preencher", "preenchido pelo agente durante o bootstrap.md"):
                return raw
    # Fallback: config.json (sub-agentes) ou o próprio id
    if agent_id != "MoltyClaw":
        cfg = os.path.join(MOLTY_DIR, "agents", agent_id, "config.json")
        if os.path.exists(cfg):
            try:
                import json
                with open(cfg, "r", encoding="utf-8") as f:
                    name = json.load(f).get("name", "").strip()
                if name:
                    return name
            except Exception:
                pass
    return agent_id


def sanitize_for_ascii(name: str, max_len: int = 12) -> str:
    """Normaliza para FIGlet: remove acentos, maiúsculas, trunca."""
    name = unicodedata.normalize("NFKD", name or "")
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"[^A-Za-z0-9 _\-]", "", name).strip().upper()
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = "MOLTYCLAW"
    return name[:max_len]


def generate_ascii(name: str) -> str:
    """Gera banner ANSI Shadow via pyfiglet, com fallback seguro."""
    clean = sanitize_for_ascii(name)
    try:
        import pyfiglet
        art = pyfiglet.figlet_format(clean, font="ansi_shadow", width=200)
        # Remove linhas totalmente vazias no fim (pyfiglet adiciona padding)
        lines = art.rstrip().split("\n")
        return "\n".join(lines)
    except Exception:
        return clean


def get_banner(agent_id: str = "MoltyClaw") -> dict:
    name = resolve_display_name(agent_id)
    return {"name": name, "ascii": generate_ascii(name)}
