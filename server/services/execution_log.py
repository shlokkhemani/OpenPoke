from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from ..config import get_settings
from ..logging_config import logger

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FMT)


def _slugify(name: str) -> str:
    cleaned = [ch.lower() if ch.isalnum() else "-" for ch in name.strip()]
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "agent"


class ExecutionAgentLogStore:
    """Simple append-only journals for execution agents."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "execution agent log directory creation failed",
                extra={"error": str(exc), "dir": str(self._base_dir)},
            )

    def _lock_for(self, agent_name: str) -> threading.Lock:
        slug = _slugify(agent_name)
        with self._global_lock:
            lock = self._locks.get(slug)
            if lock is None:
                lock = threading.Lock()
                self._locks[slug] = lock
            return lock

    def _log_path(self, agent_name: str) -> Path:
        return self._base_dir / f"{_slugify(agent_name)}.log"

    def _append_line(self, agent_name: str, tag: str, message: str) -> None:
        record = {
            "timestamp": _utc_now(),
            "tag": tag,
            "message": message,
        }
        payload = json.dumps(record, ensure_ascii=False)
        path = self._log_path(agent_name)
        lock = self._lock_for(agent_name)
        with lock:
            try:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.write("\n")
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "execution agent log append failed",
                    extra={"error": str(exc), "agent": agent_name, "path": str(path)},
                )

    def record_request(self, agent_name: str, instructions: str) -> None:
        self._append_line(agent_name, "request", instructions)

    def record_action(self, agent_name: str, description: str) -> None:
        self._append_line(agent_name, "action", description)

    def load_recent(self, agent_name: str, limit: int = 10) -> List[Dict[str, str]]:
        path = self._log_path(agent_name)
        lock = self._lock_for(agent_name)
        with lock:
            if not path.exists():
                return []
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "execution agent log read failed",
                    extra={"error": str(exc), "agent": agent_name, "path": str(path)},
                )
                return []

        entries: List[Dict[str, str]] = []
        for raw in lines[-limit:]:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    entries.append(
                        {
                            "timestamp": str(data.get("timestamp", "")),
                            "tag": str(data.get("tag", "")),
                            "message": str(data.get("message", "")),
                        }
                    )
            except Exception:
                continue
        return entries

    def list_agents(self) -> List[str]:
        try:
            files = list(self._base_dir.glob("*.log"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(
                "execution agent log listing failed",
                extra={"error": str(exc), "dir": str(self._base_dir)},
            )
            return []
        return sorted(path.stem for path in files)


_execution_agent_logs = ExecutionAgentLogStore(get_settings().resolved_execution_agents_dir)


def get_execution_agent_logs() -> ExecutionAgentLogStore:
    return _execution_agent_logs


__all__ = ["ExecutionAgentLogStore", "get_execution_agent_logs"]
