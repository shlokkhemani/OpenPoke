"""Simplified execution agent log management."""

import json
import threading
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Dict, List

from ..config import get_settings
from ..logging_config import logger


def _utc_now() -> str:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(name: str) -> str:
    """Convert agent name to filesystem-safe slug."""
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "agent"


def handle_errors(operation: str):
    """Decorator for consistent error handling and logging."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                logger.error(
                    f"execution agent {operation} failed",
                    extra={"error": str(exc), "args": args[:2] if args else None}
                )
                if operation.startswith("load"):
                    return [] if "list" in operation else None
        return wrapper
    return decorator


class ExecutionAgentLogStore:
    """Append-only journal for execution agents with simplified error handling."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._ensure_directory()

    @handle_errors("directory creation")
    def _ensure_directory(self) -> None:
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _lock_for(self, agent_name: str) -> threading.Lock:
        """Get or create a lock for an agent."""
        slug = _slugify(agent_name)
        with self._global_lock:
            if slug not in self._locks:
                self._locks[slug] = threading.Lock()
            return self._locks[slug]

    def _log_path(self, agent_name: str) -> Path:
        """Get log file path for an agent."""
        return self._base_dir / f"{_slugify(agent_name)}.log"

    @handle_errors("log append")
    def _append_line(self, agent_name: str, tag: str, message: str) -> None:
        """Append a log entry."""
        record = {"timestamp": _utc_now(), "tag": tag, "message": message}
        with self._lock_for(agent_name):
            with self._log_path(agent_name).open("a", encoding="utf-8") as f:
                f.write(f"{json.dumps(record, ensure_ascii=False)}\n")

    def record_request(self, agent_name: str, instructions: str) -> None:
        """Record an incoming request."""
        self._append_line(agent_name, "request", instructions)

    def record_action(self, agent_name: str, description: str) -> None:
        """Record an agent action."""
        self._append_line(agent_name, "action", description)

    @handle_errors("load recent")
    def load_recent(self, agent_name: str, limit: int = 10) -> List[Dict[str, str]]:
        """Load recent log entries."""
        path = self._log_path(agent_name)
        with self._lock_for(agent_name):
            if not path.exists():
                return []
            lines = path.read_text(encoding="utf-8").splitlines()

        entries = []
        for raw in lines[-limit:]:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    entries.append({
                        "timestamp": str(data.get("timestamp", "")),
                        "tag": str(data.get("tag", "")),
                        "message": str(data.get("message", "")),
                    })
            except (json.JSONDecodeError, AttributeError):
                continue
        return entries

    @handle_errors("list agents")
    def list_agents(self) -> List[str]:
        """List all agents with logs."""
        files = list(self._base_dir.glob("*.log"))
        return sorted(path.stem for path in files)


_execution_agent_logs = ExecutionAgentLogStore(get_settings().resolved_execution_agents_dir)


def get_execution_agent_logs() -> ExecutionAgentLogStore:
    """Get the singleton log store instance."""
    return _execution_agent_logs