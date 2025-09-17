import json
import os
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
from urllib.request import Request, urlopen


OpenRouterBaseURL = "https://openrouter.ai/api/v1"


def _norm_tools(
    tools: Optional[Union[List[str], List[Dict[str, Any]]]]
) -> Optional[List[Dict[str, Any]]]:
    if not tools:
        return None
    norm: List[Dict[str, Any]] = []
    for t in tools:
        if isinstance(t, str):
            norm.append(
                {
                    "type": "function",
                    "function": {
                        "name": t,
                        "description": "",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                }
            )
        elif isinstance(t, dict):
            # Assume already OpenAI-compatible tool schema
            norm.append(t)
        else:
            raise TypeError("tools must be a list of strings or dicts")
    return norm


def _norm_messages(
    messages: List[Dict[str, Any]], system: Optional[str]
) -> List[Dict[str, Any]]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    # pass-through but do a light validation
    for m in messages:
        if not isinstance(m, dict) or "role" not in m or "content" not in m:
            raise ValueError("each message must be a dict with 'role' and 'content'")
        msgs.append(m)
    return msgs


def _norm_structured(
    structured: Optional[Union[Dict[str, Any], Tuple[str, Dict[str, Any], Optional[bool]]]]
) -> Optional[Dict[str, Any]]:
    """Normalize structured output into OpenAI-compatible response_format.

    Accepts:
    - dict with keys {"name", "schema", "strict"} OR a raw JSON Schema dict
    - tuple (name, schema, strict?)
    """
    if not structured:
        return None

    if isinstance(structured, tuple):
        name, schema, strict = structured if len(structured) == 3 else (structured[0], structured[1], True)
        return {
            "type": "json_schema",
            "json_schema": {"name": name, "schema": schema, "strict": True if strict is None else bool(strict)},
        }

    if isinstance(structured, dict):
        if "json_schema" in structured and structured.get("type") == "json_schema":
            return structured  # already normalized
        if "name" in structured and "schema" in structured:
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": structured["name"],
                    "schema": structured["schema"],
                    "strict": bool(structured.get("strict", True)),
                },
            }
        # treat as raw JSON Schema root, wrap with a default name
        return {
            "type": "json_schema",
            "json_schema": {"name": "AutoSchema", "schema": structured, "strict": True},
        }

    raise TypeError("structured must be a dict or (name, schema, strict?) tuple")


def _headers(extra_headers: Optional[Dict[str, str]] = None, api_key: Optional[str] = None) -> Dict[str, str]:
    key = api_key or os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set and api_key not provided")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    # Helpful optional headers per OpenRouter recommendations
    ref = os.getenv("OPENROUTER_HTTP_REFERER")
    if ref:
        headers["HTTP-Referer"] = ref
    title = os.getenv("OPENROUTER_APP_TITLE")
    if title:
        headers["X-Title"] = title
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _do_post(url: str, payload: Dict[str, Any], headers: Dict[str, str]):
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    return urlopen(req)


def _sse_events(response) -> Iterator[str]:
    """Iterate Server-Sent Events as raw event payload strings.

    Groups lines until a blank line; collects all 'data:' lines and joins them with '\n'.
    """
    buf = []
    while True:
        line = response.readline()
        if not line:
            # flush remaining
            if buf:
                yield "\n".join(buf)
            break
        try:
            s = line.decode("utf-8", errors="ignore").rstrip("\n")
        except Exception:
            s = str(line)
        if s == "":
            if buf:
                # emit event
                yield "\n".join(buf)
                buf = []
            continue
        if s.startswith(":"):
            # comment/keepalive
            continue
        if s.startswith("data:"):
            buf.append(s[5:].lstrip())
        # we ignore 'event:' and others for OpenAI-compatible streams


def _default_stream_adapter(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAI-like stream chunk to a simple delta structure.

    Returns one of:
    - {"type":"content","text":str}
    - {"type":"tool_call","tool_name":str,"arguments":str,"index":int}
    - {"type":"event","event":str} for control events like DONE
    """
    choices = chunk.get("choices", [])
    if not choices:
        return {"type": "event", "event": "noop"}
    delta = choices[0].get("delta", {})
    if "tool_calls" in delta:
        tc = delta["tool_calls"][0]
        fn = (tc.get("function") or {})
        return {
            "type": "tool_call",
            "tool_name": fn.get("name"),
            "arguments": fn.get("arguments", ""),
            "index": tc.get("index", 0),
        }
    if "content" in delta and delta["content"] is not None:
        return {"type": "content", "text": delta["content"]}
    return {"type": "event", "event": "noop"}


def stream_chat_completion(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    tools: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    structured: Optional[Union[Dict[str, Any], Tuple[str, Dict[str, Any], Optional[bool]]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    parallel_tool_calls: Optional[bool] = None,
    base_url: str = OpenRouterBaseURL,
    extra_headers: Optional[Dict[str, str]] = None,
    api_key: Optional[str] = None,
) -> Iterator[Dict[str, Any]]:
    """Stream chat completions from OpenRouter as a generator of deltas.

    Env:
    - `OPENROUTER_API_KEY` for authentication
    - optional `OPENROUTER_HTTP_REFERER`, `OPENROUTER_APP_TITLE`

    Yields small dicts representing content/tool-call deltas.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": _norm_messages(messages, system),
        "stream": True,
    }
    if tools:
        payload["tools"] = _norm_tools(tools)
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        payload["parallel_tool_calls"] = bool(parallel_tool_calls)
    rf = _norm_structured(structured)
    if rf:
        payload["response_format"] = rf
    if temperature is not None:
        payload["temperature"] = float(temperature)
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    resp = _do_post(url, payload, _headers(extra_headers, api_key))
    try:
        for raw in _sse_events(resp):
            if not raw:
                continue
            if raw.strip() == "[DONE]":
                yield {"type": "event", "event": "done"}
                break
            try:
                chunk = json.loads(raw)
            except json.JSONDecodeError:
                # some providers send keepalives or mixed lines
                continue
            # Emit finish events when present
            try:
                choices = chunk.get("choices", [])
                if choices and "finish_reason" in choices[0] and choices[0]["finish_reason"]:
                    yield {"type": "event", "event": "finish", "reason": choices[0]["finish_reason"]}
            except Exception:
                pass
            # Emit content/tool deltas
            yield _default_stream_adapter(chunk)
    finally:
        try:
            resp.close()
        except Exception:
            pass


def chat_completion(
    *,
    model: str,
    messages: List[Dict[str, Any]],
    system: Optional[str] = None,
    tools: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
    structured: Optional[Union[Dict[str, Any], Tuple[str, Dict[str, Any], Optional[bool]]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    parallel_tool_calls: Optional[bool] = None,
    base_url: str = OpenRouterBaseURL,
    extra_headers: Optional[Dict[str, str]] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """One-shot chat completion call to OpenRouter.

    Returns OpenAI-compatible response JSON with added convenience keys:
    - `text`: assistant text (if any)
    - `tool_calls`: list of tool calls (if any)

    For structured outputs, if the model returns a JSON string, `text_json` will
    attempt to parse it into a Python object.
    """
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload: Dict[str, Any] = {
        "model": model,
        "messages": _norm_messages(messages, system),
        "stream": False,
    }
    if tools:
        payload["tools"] = _norm_tools(tools)
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        payload["parallel_tool_calls"] = bool(parallel_tool_calls)
    rf = _norm_structured(structured)
    if rf:
        payload["response_format"] = rf
    if temperature is not None:
        payload["temperature"] = float(temperature)
    if max_tokens is not None:
        payload["max_tokens"] = int(max_tokens)

    try:
        resp = _do_post(url, payload, _headers(extra_headers, api_key))
        raw = resp.read()
    finally:
        try:
            resp.close()
        except Exception:
            pass

    try:
        data = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception as e:
        raise RuntimeError(f"failed to decode response: {e}")

    # Convenience extras
    try:
        choice0 = (data.get("choices") or [{}])[0]
        msg = choice0.get("message", {})
        text = msg.get("content")
        tool_calls = msg.get("tool_calls") or []
        data["text"] = text
        data["tool_calls"] = tool_calls
        if text:
            try:
                data["text_json"] = json.loads(text)
            except Exception:
                pass
    except Exception:
        pass
    return data


def build_tool_result_message(*, tool_call_id: str, content: Union[str, Dict[str, Any], List[Any]]) -> Dict[str, Any]:
    """Helper to create a tool role message to feed back into messages.

    - `tool_call_id`: the id from the assistant's tool_calls[].id
    - `content`: string or JSON-serializable payload
    """
    if not isinstance(content, str):
        try:
            content = json.dumps(content)
        except Exception:
            content = str(content)
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


__all__ = [
    "chat_completion",
    "stream_chat_completion",
    "OpenRouterBaseURL",
    "build_tool_result_message",
]
