"""Execution agent log management with structured XML-style tags."""

import threading
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

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


def _encode_payload(payload: str) -> str:
    """Encode payload for storage."""
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    """Decode payload from storage."""
    return unescape(payload).replace("\\n", "\n")


class ExecutionAgentLogStore:
    """Append-only journal for execution agents with XML-style tags."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning(f"Failed to create directory: {exc}")

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

    def _append(self, agent_name: str, tag: str, payload: str) -> None:
        """Append an entry with the given tag."""
        encoded = _encode_payload(str(payload))
        entry = f"<{tag}>{encoded}</{tag}>\n"

        with self._lock_for(agent_name):
            try:
                with self._log_path(agent_name).open("a", encoding="utf-8") as f:
                    f.write(entry)
            except Exception as exc:
                logger.error(f"Failed to append to log: {exc}")

    def _parse_line(self, line: str) -> Optional[Tuple[str, str]]:
        """Parse a single log line."""
        stripped = line.strip()
        if not (stripped.startswith("<") and "</" in stripped):
            return None

        open_end = stripped.find(">")
        close_start = stripped.rfind("</")
        close_end = stripped.rfind(">")

        if open_end == -1 or close_start == -1 or close_end == -1:
            return None

        tag = stripped[1:open_end]
        closing_tag = stripped[close_start + 2 : close_end]

        if closing_tag != tag:
            return None

        return tag, _decode_payload(stripped[open_end + 1 : close_start])

    def record_request(self, agent_name: str, instructions: str) -> None:
        """Record an incoming request from the interaction agent."""
        self._append(agent_name, "agent request", f"[{_utc_now()}] {instructions}")

    def record_action(self, agent_name: str, description: str) -> None:
        """Record an agent action (tool call)."""
        self._append(agent_name, "action", description)

    def record_tool_response(self, agent_name: str, tool_name: str, response: str) -> None:
        """Record the response from a tool."""
        self._append(agent_name, "tool response", f"{tool_name}: {response}")

    def record_agent_response(self, agent_name: str, response: str) -> None:
        """Record the agent's final response."""
        self._append(agent_name, "agent response", f"[{_utc_now()}] {response}")

    def iter_entries(self, agent_name: str) -> Iterator[Tuple[str, str]]:
        """Iterate over all log entries for an agent."""
        path = self._log_path(agent_name)
        with self._lock_for(agent_name):
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                lines = []
            except Exception as exc:
                logger.error(f"Failed to read log: {exc}")
                lines = []

        for line in lines:
            parsed = self._parse_line(line)
            if parsed is not None:
                yield parsed

    def load_transcript(self, agent_name: str) -> str:
        """Load the full transcript for inclusion in system prompt."""
        return "\n".join(
            f"<{tag}>{escape(payload, quote=False)}</{tag}>"
            for tag, payload in self.iter_entries(agent_name)
        )

    def load_recent(self, agent_name: str, limit: int = 10) -> list[tuple[str, str]]:
        """Load recent log entries."""
        entries = list(self.iter_entries(agent_name))
        return entries[-limit:] if entries else []

    def list_agents(self) -> list[str]:
        """List all agents with logs."""
        try:
            return sorted(path.stem for path in self._base_dir.glob("*.log"))
        except Exception as exc:
            logger.error(f"Failed to list agents: {exc}")
            return []

    def clear_all(self) -> None:
        """Clear all execution agent logs."""
        try:
            for log_file in self._base_dir.glob("*.log"):
                log_file.unlink()
            logger.info("Cleared all execution agent logs")
        except Exception as exc:
            logger.error(f"Failed to clear execution logs: {exc}")


_execution_agent_logs = ExecutionAgentLogStore(get_settings().resolved_execution_agents_dir)


def get_execution_agent_logs() -> ExecutionAgentLogStore:
    """Get the singleton log store instance."""
    return _execution_agent_logs