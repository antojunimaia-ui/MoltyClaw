"""
Tool Parser Universal do MoltyClaw.
Interpreta e normaliza chamadas de ferramentas geradas por qualquer modelo de IA,
mesmo quando o modelo desobedece a sintaxe estrita ou usa formatos próprios
como <tool_call>, <function_call>, <invoke>, blocos markdown ou XML.
"""

import re
import json
from typing import Optional, Dict, Any


_SEARCH_SYNONYMS = {
    "DUCKDUCKGO_SEARCH", "SEARCH", "WEB_SEARCH", "DDG",
    "GOOGLE_SEARCH", "INTERNET_SEARCH", "BUSCA", "PESQUISA"
}

_CMD_SYNONYMS = {
    "EXECUTE_COMMAND", "TERMINAL", "SHELL", "BASH",
    "RUN_COMMAND", "CMD_RUN", "EXEC"
}

_NAV_SYNONYMS = {
    "NAVIGATE", "OPEN_URL", "BROWSE", "VISIT", "GO_TO"
}

_CANVAS_SYNONYMS = {
    "CANVAS", "UPDATE_CANVAS", "RENDER_CANVAS", "CANVAS_PREVIEW"
}


def parse_llm_tool_call(response: str) -> Optional[Dict[str, Any]]:
    """
    Analisa a resposta bruta da LLM e extrai uma chamada de ferramenta normalizada.
    Retorna um dicionário no formato:
    {
        "action": str,
        "param": str,
        ... outros campos preservados (ex: filename, content, server, etc.)
    }
    ou None se nenhuma chamada de ferramenta for detectada.
    """
    if not response or not isinstance(response, str):
        return None

    # 1. Tag padrão <tool> ... </tool>
    m = re.search(r'<tool>\s*(.*?)\s*</tool>', response, re.DOTALL | re.IGNORECASE)
    if m:
        parsed = _try_parse_payload(m.group(1).strip())
        if parsed:
            return parsed

    # 2. Tag <tool_call> ... </tool_call> (Ling, Qwen, Hermes, DeepSeek, etc.)
    m = re.search(r'<tool_call>\s*(.*?)\s*</tool_call>', response, re.DOTALL | re.IGNORECASE)
    if m:
        parsed = _try_parse_payload(m.group(1).strip())
        if parsed:
            return parsed

    # 3. Tag <function_call> ... </function_call>
    m = re.search(r'<function_call>\s*(.*?)\s*</function_call>', response, re.DOTALL | re.IGNORECASE)
    if m:
        parsed = _try_parse_payload(m.group(1).strip())
        if parsed:
            return parsed

    # 4. Formatos DSML / Anthropic XML (<invoke name="...">...</invoke>)
    dsml = re.search(
        r'<invoke[^>]*?name=["\']?([A-Za-z0-9_]+)["\']?[^>]*>(.*?)</invoke>',
        response, re.DOTALL | re.IGNORECASE
    )
    if dsml:
        action = dsml.group(1).strip()
        body = dsml.group(2).strip()
        param_m = re.search(r'<parameter[^>]*>(.*?)</parameter>', body, re.DOTALL | re.IGNORECASE)
        param = param_m.group(1).strip() if param_m else re.sub(r'<[^>]+>', '', body).strip()
        return _normalize_tool_dict({"action": action, "param": param})

    # 5. Formato <action>NOME</action> <param>...</param>
    act_tag = re.search(
        r'<action>\s*([A-Za-z0-9_]+)\s*</action>.*?(?:<param>\s*(.*?)\s*</param>)?',
        response, re.DOTALL | re.IGNORECASE
    )
    if act_tag:
        action = act_tag.group(1).strip()
        param = (act_tag.group(2) or "").strip()
        return _normalize_tool_dict({"action": action, "param": param})

    # 6. Bloco Markdown JSON: ```json { ... } ```
    for block in re.finditer(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL):
        try:
            cand = json.loads(block.group(1).strip())
            normalized = _normalize_tool_dict(cand)
            if normalized:
                return normalized
        except Exception:
            pass

    # 7. JSON solto na resposta contendo chaves explícitas de ferramenta
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(response):
        start = response.find('{', idx)
        if start == -1:
            break
        try:
            data, end = decoder.raw_decode(response[start:])
            normalized = _normalize_tool_dict(data)
            if normalized:
                return normalized
            idx = start + 1
        except Exception:
            idx = start + 1

    return None


def _try_parse_payload(raw: str) -> Optional[Dict[str, Any]]:
    """Tenta decodificar o conteúdo interno de uma tag de ferramenta."""
    if not raw:
        return None

    # Remove fences de markdown se houver
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    # Tentativa 1: JSON direto
    if raw.startswith("{") and raw.endswith("}"):
        try:
            data = json.loads(raw)
            return _normalize_tool_dict(data)
        except Exception:
            pass

    # Tentativa 2: Formato XML com arg_key / arg_value (típico do Ling, Qwen, etc.)
    # Exemplo:
    # DDG_SEARCH
    # <arg_key>busca</arg_key>
    # <arg_value>quando lança o Gemini 4</arg_value>
    arg_val_match = re.search(r'<arg_value>(.*?)</arg_value>', raw, re.DOTALL | re.IGNORECASE)
    if arg_val_match:
        action_match = re.search(r'^([^<\s\n]+)', raw)
        action = action_match.group(1).strip() if action_match else "DDG_SEARCH"
        param = arg_val_match.group(1).strip()
        return _normalize_tool_dict({"action": action, "param": param})

    # Tentativa 3: Formato com tags genéricas <name>...</name> e <param>...</param>
    name_m = re.search(r'<(?:name|action|tool)>([^<]+)</(?:name|action|tool)>', raw, re.IGNORECASE)
    if name_m:
        action = name_m.group(1).strip()
        param_m = re.search(
            r'<(?:param|arguments|value|query|input)>(.*?)</(?:param|arguments|value|query|input)>',
            raw, re.DOTALL | re.IGNORECASE
        )
        param = param_m.group(1).strip() if param_m else ""
        return _normalize_tool_dict({"action": action, "param": param})

    # Tentativa 4: Chamada textual pura, ex:
    # DDG_SEARCH: "termo de busca"
    # GOTO: https://exemplo.com
    # DDG_SEARCH("termo")
    line_m = re.search(r'^([A-Za-z_]{3,})\s*[:\(-]\s*(.+?)(?:\)|$)', raw, re.DOTALL)
    if line_m:
        action = line_m.group(1).strip()
        param = line_m.group(2).strip().strip('"\'')
        return _normalize_tool_dict({"action": action, "param": param})

    return None


def _normalize_tool_dict(data: Any) -> Optional[Dict[str, Any]]:
    """Normaliza nomes de ação e argumentos para o padrão aceito pelo MoltyClaw."""
    if not isinstance(data, dict):
        return None

    # Mapeamento de chave de ação
    action = (
        data.get("action") or
        data.get("name") or
        data.get("tool") or
        data.get("function") or
        data.get("tool_name")
    )
    if not action:
        return None
    action = str(action).strip()

    # Normalização de ação para caixa alta
    action_upper = action.upper()

    if action_upper in _SEARCH_SYNONYMS:
        action = "DDG_SEARCH"
    elif action_upper in _CMD_SYNONYMS:
        action = "CMD"
    elif action_upper in _NAV_SYNONYMS:
        action = "GOTO"
    elif action_upper in _CANVAS_SYNONYMS:
        action = "CANVAS_UPDATE"
    elif action_upper == "SKILL_USE":
        # Suporte a skill_use legado
        skill_input = data.get("input", {})
        query = skill_input.get("query", str(skill_input)) if isinstance(skill_input, dict) else str(skill_input)
        return {"action": "DDG_SEARCH", "param": query}
    else:
        action = action_upper

    # Mapeamento de parâmetro
    param = ""
    if "param" in data:
        param = data["param"]
    elif "arguments" in data:
        args = data["arguments"]
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                param = args
        if isinstance(args, dict):
            for key in ["query", "busca", "search", "q", "url", "cmd", "command", "param", "value", "prompt", "input"]:
                if key in args:
                    param = args[key]
                    break
            if not param:
                for v in args.values():
                    if isinstance(v, (str, int, float)):
                        param = str(v)
                        break
    elif "input" in data:
        inp = data["input"]
        if isinstance(inp, dict):
            param = inp.get("query") or inp.get("busca") or inp.get("param") or str(inp)
        else:
            param = str(inp)
    elif "parameters" in data:
        params = data["parameters"]
        if isinstance(params, dict):
            param = params.get("query") or params.get("busca") or params.get("param") or str(params)
        else:
            param = str(params)
    elif "busca" in data:
        param = data["busca"]
    elif "query" in data:
        param = data["query"]

    result = dict(data)
    result["action"] = action
    result["param"] = str(param) if not isinstance(param, (dict, list)) else json.dumps(param)
    return result
