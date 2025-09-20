"""Task registry for execution agents."""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from .search_email.schemas import get_schemas as _get_email_search_schemas
from .search_email.tool import build_registry as _build_email_search_registry


def get_task_schemas() -> List[Dict[str, Any]]:
    """Return tool schemas contributed by task modules."""

    return [*_get_email_search_schemas()]


def get_task_registry(agent_name: str) -> Dict[str, Callable[..., Any]]:
    """Return executable task tools keyed by name."""

    registry: Dict[str, Callable[..., Any]] = {}
    registry.update(_build_email_search_registry(agent_name))
    return registry


__all__ = [
    "get_task_registry",
    "get_task_schemas",
]
