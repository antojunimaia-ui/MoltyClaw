import os
import sys
import json
import asyncio
import re
import aiohttp
from rich.console import Console

try:
    from mistralai.models.chat_completion import ChatMessage
except ImportError:
    ChatMessage = None

default_console = Console()

class KodaCloudResponse:
    def __init__(self, session, url, payload, console=None):
        self.session = session
        self.url = url
        self.payload = payload
        self.console = console or default_console

    async def __aiter__(self):
        try:
            async with self.session.post(
                self.url,
                json=self.payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.console.print(f"[error]>> [Koda Cloud] Error response: {error_text[:500]}[/error]")
                    raise Exception(f"Koda Cloud Error ({response.status}): {error_text[:200]}")

                buffer = ""
                async for chunk in response.content.iter_any():
                    try:
                        decoded = chunk.decode('utf-8')
                        buffer += decoded

                        while '\n' in buffer:
                            line_text, buffer = buffer.split('\n', 1)
                            line_text = line_text.strip()

                            if not line_text or not line_text.startswith('data: '):
                                continue

                            data_str = line_text[6:].strip()
                            if data_str == '[DONE]':
                                return

                            try:
                                data = json.loads(data_str)
                                if data.get('type') == 'text' and data.get('content'):
                                    class Choice:
                                        def __init__(self, content):
                                            self.delta = type('obj', (object,), {'content': content})()
                                    yield type('obj', (object,), {'choices': [Choice(data['content'])]})()
                                elif data.get('type') == 'done':
                                    return
                            except json.JSONDecodeError as e:
                                self.console.print(f"[warning]>> [Koda Cloud] JSON decode error: {e} - data: {data_str[:100]}[/warning]")
                                continue
                    except Exception:
                        continue
        finally:
            if not self.session.closed:
                await self.session.close()

def extract_text(chunk, provider=None):
    try:
        if provider == "gemini":
            return chunk.text

        if hasattr(chunk, "data") and isinstance(chunk.data, str):
            if chunk.data == "[DONE]":
                return None
            d = json.loads(chunk.data)
            if "choices" in d and len(d["choices"]) > 0:
                delta = d["choices"][0].get("delta", {})
                return delta.get("content", "")
        elif hasattr(chunk, "data") and hasattr(chunk.data, "choices") and chunk.data.choices:
            return chunk.data.choices[0].delta.content
        elif hasattr(chunk, "choices") and getattr(chunk, "choices", None):
            return chunk.choices[0].delta.content
        elif hasattr(chunk, "index") and hasattr(chunk.delta):
            return chunk.delta.content
        elif hasattr(chunk, "content"):
            return chunk.content
        elif isinstance(chunk, dict) and "message" in chunk:
            return chunk["message"].get("content", "")
        elif hasattr(chunk, "get") and chunk.get("message"):
            return chunk.get("message", {}).get("content", "")
    except Exception:
        pass
    return None

async def stream_llm(
    provider: str,
    model: str,
    history: list,
    mistral_client=None,
    openai_client=None,
    gemini_client=None,
    ollama_client=None,
    stream_callback=None,
    silent: bool = False,
    console=None
) -> str:
    con = console or default_console
    async_response = None
    kodacloud_session = None

    if provider == "mistral":
        sanitized_history = []
        last_role = None
        for msg in history:
            role = msg["role"]
            content = str(msg.get("content") or "").strip()
            if not content:
                content = "..."
            if role == "system":
                sanitized_history.append({"role": "system", "content": content})
                continue
            if role == last_role:
                if sanitized_history:
                    sanitized_history[-1]["content"] += "\n" + content
                continue
            sanitized_history.append({"role": role, "content": content})
            last_role = role

        for _retry in range(4):
            try:
                if hasattr(mistral_client, 'chat'):
                    if hasattr(mistral_client.chat, 'stream_async'):
                        method = mistral_client.chat.stream_async
                    else:
                        method = getattr(mistral_client.chat, 'stream')
                    res_or_coro = method(model=model, messages=sanitized_history)
                    if asyncio.iscoroutine(res_or_coro) or hasattr(res_or_coro, '__await__'):
                        async_response = await res_or_coro
                    else:
                        async_response = res_or_coro
                else:
                    converted_legacy = [ChatMessage(role=m["role"], content=m["content"]) for m in sanitized_history] if ChatMessage else sanitized_history
                    async_response = mistral_client.chat_stream(model=model, messages=converted_legacy)
                break
            except Exception as e:
                if _retry < 3:
                    con.print(f"[warning]>> Instabilidade na API Mistral detectada (Erro {str(e)[:40]}...) - Reconectando em breve...[/warning]")
                    await asyncio.sleep(2 + _retry)
                else:
                    raise e

    elif provider == "gemini":
        for _retry in range(4):
            try:
                contents = []
                for m in history:
                    if m["role"] == "system":
                        continue
                    role = "user" if m["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [m["content"]]})
                async_response = await gemini_client.generate_content_async(contents, stream=True)
                break
            except Exception as e:
                if _retry < 3:
                    con.print(f"[warning]>> Instabilidade na API Gemini detectada (Erro {str(e)[:40]}...) - Reconectando em breve...[/warning]")
                    await asyncio.sleep(2 + _retry)
                else:
                    raise e

    elif provider == "ollama":
        for _retry in range(4):
            try:
                async_response = await ollama_client.chat(model=model, messages=history, stream=True)
                break
            except Exception as e:
                if _retry < 3:
                    con.print(f"[warning]>> Instabilidade no Ollama detectada (Erro {str(e)[:40]}...) - Verifique se o serviço está rodando.[/warning]")
                    await asyncio.sleep(2 + _retry)
                else:
                    raise e

    else:
        for _retry in range(4):
            try:
                if provider == "kodacloud":
                    payload = {"model": model, "messages": history, "stream": True}
                    kodacloud_session = aiohttp.ClientSession()
                    async_response = KodaCloudResponse(
                        kodacloud_session,
                        "http://cn-01.hostzera.com.br:2137/v1/chat",
                        payload,
                        console=con
                    )
                else:
                    async_response = await openai_client.chat.completions.create(
                        model=model,
                        messages=history,
                        stream=True
                    )
                break
            except Exception as e:
                if _retry < 3:
                    provider_name = "Koda Cloud" if provider == "kodacloud" else ("OpenCode Zen" if provider == "opencode" else "OpenRouter")
                    error_msg = str(e)
                    if "<!DOCTYPE html>" in error_msg or "<html" in error_msg:
                        con.print(f"[warning]>> {provider_name} retornou HTML em vez de JSON. Servidor pode estar offline ou endpoint incorreto.[/warning]")
                    else:
                        con.print(f"[warning]>> Instabilidade na API {provider_name} detectada (Erro {error_msg[:80]}...) - Reconectando em breve...[/warning]")
                    await asyncio.sleep(2 + _retry)
                else:
                    raise e

    in_tool_mode = False
    in_think_mode = False
    buffer_txt = ""
    response_chunks = ""

    _TOOL_STARTS = ("<tool>", "<tool_call>", "<function_call>", "<invoke")
    _TOOL_ENDS = ("</tool>", "</tool_call>", "</function_call>", "</invoke>", "/>")
    _ORPHAN_TAGS = ("</think>", "</tool>", "</tool_call>", "</function_call>", "</invoke>")

    async def process_chunk_text(text, _buffer_txt, _in_tool_mode, _in_think_mode, _response_chunks):
        if not text:
            return _buffer_txt, _in_tool_mode, _in_think_mode, _response_chunks
        _response_chunks += text
        for char in text:
            _buffer_txt += char
            if not _in_tool_mode and not _in_think_mode:
                if _buffer_txt.startswith("<"):
                    if "<think>".startswith(_buffer_txt):
                        if _buffer_txt == "<think>":
                            _in_think_mode = True
                            _buffer_txt = ""
                        continue
                    if any(tag.startswith(_buffer_txt) for tag in _TOOL_STARTS):
                        if any(_buffer_txt == tag for tag in _TOOL_STARTS):
                            _in_tool_mode = True
                            _buffer_txt = ""
                        continue
                    if any(tag.startswith(_buffer_txt) for tag in _ORPHAN_TAGS):
                        if any(_buffer_txt == tag for tag in _ORPHAN_TAGS):
                            _buffer_txt = ""
                        continue
                if not silent:
                    print(_buffer_txt, end="", flush=True)
                if stream_callback:
                    await stream_callback(_buffer_txt)
                _buffer_txt = ""
            elif _in_tool_mode:
                if any(_buffer_txt.endswith(end_tag) for end_tag in _TOOL_ENDS):
                    _in_tool_mode = False
                    _buffer_txt = ""
            elif _in_think_mode:
                if _buffer_txt.endswith("</think>"):
                    _in_think_mode = False
                    _buffer_txt = ""
        return _buffer_txt, _in_tool_mode, _in_think_mode, _response_chunks

    try:
        if hasattr(async_response, '__aiter__'):
            async for chunk in async_response:
                t = extract_text(chunk, provider)
                if t:
                    buffer_txt, in_tool_mode, in_think_mode, response_chunks = await process_chunk_text(
                        t, buffer_txt, in_tool_mode, in_think_mode, response_chunks
                    )
        elif hasattr(async_response, '__iter__'):
            for chunk in async_response:
                t = extract_text(chunk, provider)
                if t:
                    buffer_txt, in_tool_mode, in_think_mode, response_chunks = await process_chunk_text(
                        t, buffer_txt, in_tool_mode, in_think_mode, response_chunks
                    )
                await asyncio.sleep(0.01)
    finally:
        if kodacloud_session and not kodacloud_session.closed:
            try:
                await kodacloud_session.close()
            except Exception:
                pass

    return response_chunks