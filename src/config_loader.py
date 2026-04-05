import os
import json
import re
from typing import Any, Dict

def strip_comments(text: str) -> str:
    """Remove comentários estilo JSON5 (// e /* */) da string."""
    # Remove /* */
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Remove //
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        # Regex para pegar o // que não esteja dentro de aspas (simplificado)
        parts = re.split(r'(?<!:)\s*//', line)
        cleaned_lines.append(parts[0])
    return "\n".join(cleaned_lines)

def env_substitution(data: Any) -> Any:
    """Substitui recursivamente ${VAR} por variáveis de ambiente."""
    if isinstance(data, str):
        # Encontra padrões ${VAR} ou ${VAR:default}
        pattern = re.compile(r'\${(\w+)(?::([^}]*))?}')
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2)
            val = os.getenv(var_name)
            if val is not None:
                return val
            # Se não encontrar a variável e não tiver default, retorna vazio
            # para que o 'or os.getenv()' posterior funcione corretamente.
            return default_value if default_value is not None else ""
        return pattern.sub(replacer, data)
    elif isinstance(data, dict):
        return {k: env_substitution(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [env_substitution(i) for i in data]
    return data

def load_molty_config() -> Dict[str, Any]:
    """Carrega o moltyclaw.json da pasta base (~/.moltyclaw/moltyclaw.json)"""
    molty_dir = os.path.join(os.path.expanduser("~"), ".moltyclaw")
    config_path = os.path.join(molty_dir, "moltyclaw.json")
    
    try:
        if not os.path.exists(config_path):
            return {}
            
        with open(config_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        # Strip comments to mimic JSON5 behavior
        clean_json = strip_comments(raw_content)
        
        # Load JSON with strict=False to allow control characters (tabs, etc) commonly found in VPS edits
        data = json.loads(clean_json, strict=False)
        
        # Substitute Env Vars
        config = env_substitution(data)
        
        return config
    except Exception as e:
        import traceback
        # print(f">> [ConfigLoader] Erro ao carregar moltyclaw.json em {config_path}: {e}")
        return {}

# Singleton instance
_GLOBAL_CONFIG = None

def get_config() -> Dict[str, Any]:
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None:
        _GLOBAL_CONFIG = load_molty_config()
    return _GLOBAL_CONFIG
