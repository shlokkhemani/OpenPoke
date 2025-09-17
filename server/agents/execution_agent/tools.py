from typing import Any, Callable, Dict, List
import json
import subprocess

# OpenAI/OpenRouter-compatible tool schema list for the execution agent.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "fetch_http",
            "description": "Fetch a URL via HTTP GET and return status and body preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Absolute URL to fetch"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 60, "default": 10},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a read-only shell command and capture stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Command and args, e.g. ['bash','-lc','echo hi']",
                    },
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 60, "default": 10},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


def _impl_fetch_http(url: str, timeout: int = 10) -> Dict[str, Any]:
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(4096)
            ct = resp.headers.get("content-type", "")
            return {
                "status": resp.status,
                "content_type": ct,
                "body_preview": body[:512].decode("utf-8", errors="replace"),
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _impl_run_shell(command: List[str], timeout: int = 10) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except Exception as e:
        return {"returncode": -1, "error": str(e)}


# Registry mapping tool names to Python callables.
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "fetch_http": _impl_fetch_http,
    "run_shell": _impl_run_shell,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible tool schemas for the execution agent."""
    return TOOL_SCHEMAS


def get_tool_registry() -> Dict[str, Callable[..., Any]]:
    """Return Python callables for executing tools by name."""
    return TOOL_REGISTRY

