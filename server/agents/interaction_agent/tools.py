from typing import Any, Callable, Dict, List, Optional

# OpenAI/OpenRouter-compatible tool schema list.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": "Search a knowledge base for short factual snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "route_to_execution",
            "description": "Request that the Execution Agent handle a task (returns a routing token).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task summary to execute"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "default": "normal",
                    },
                },
                "required": ["task"],
                "additionalProperties": False,
            },
        },
    },
]


def _impl_search_kb(query: str, limit: int = 3) -> Dict[str, Any]:
    """Placeholder KB search. Replace with real search integration.

    Returns a deterministic mock result to keep server logic simple.
    """
    items = [
        {"title": f"Result {i+1}", "snippet": f"Snippet for '{query}' #{i+1}", "score": 0.5 - i * 0.1}
        for i in range(max(0, min(int(limit), 10)))
    ]
    return {"query": query, "results": items}


def _impl_route_to_execution(task: str, priority: str = "normal") -> Dict[str, str]:
    """Return a mock routing token and echoed task.

    An orchestrator can consume this token to spawn the Execution Agent.
    """
    token = f"exec::{priority}::{abs(hash(task)) % (10**8):08d}"
    return {"route": token, "task": task, "priority": priority}


# Registry mapping tool names to Python callables.
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "search_kb": _impl_search_kb,
    "route_to_execution": _impl_route_to_execution,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible tool schemas for the interaction agent."""
    return TOOL_SCHEMAS


def get_tool_registry() -> Dict[str, Callable[..., Any]]:
    """Return Python callables for executing tools by name."""
    return TOOL_REGISTRY

