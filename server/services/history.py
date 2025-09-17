from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional

from ..config import get_settings
from ..logging_config import logger

MessageDict = Dict[str, str]


class ChatHistoryStore:
    """Persist chat transcripts to disk and reload them on startup."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._history: List[MessageDict] = []
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self._history = []
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("failed to load chat history", extra={"error": str(exc), "path": str(self._path)})
            self._history = []
            return

        if isinstance(data, list):
            cleaned = [self._sanitize(item) for item in data]
            self._history = [item for item in cleaned if item]
        else:
            self._history = []

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        payload = json.dumps(self._history, ensure_ascii=False, indent=2)
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(self._path)

    @staticmethod
    def _sanitize(item: object) -> Optional[MessageDict]:
        if not isinstance(item, dict):
            return None
        role = str(item.get("role", "")).strip()
        if not role:
            return None
        content = item.get("content", "")
        if content is None:
            content = ""
        return {"role": role, "content": str(content)}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_history(self) -> List[MessageDict]:
        with self._lock:
            return list(self._history)

    def replace(self, messages: List[MessageDict]) -> None:
        cleaned = [self._sanitize(m) for m in messages]
        normalized = [msg for msg in cleaned if msg and msg["content"].strip()]
        with self._lock:
            self._history = normalized
            try:
                self._persist()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("failed to persist chat history", extra={"error": str(exc), "path": str(self._path)})

    def append(self, message: MessageDict) -> None:
        sanitized = self._sanitize(message)
        if not sanitized or not sanitized["content"].strip():
            return
        with self._lock:
            self._history.append(sanitized)
            try:
                self._persist()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("failed to persist chat history", extra={"error": str(exc), "path": str(self._path)})

    def clear(self) -> None:
        with self._lock:
            self._history = []
            try:
                if self._path.exists():
                    self._path.unlink()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("failed to clear chat history file", extra={"error": str(exc), "path": str(self._path)})


chat_history_store = ChatHistoryStore(get_settings().resolved_chat_history_path)

__all__ = ["chat_history_store", "ChatHistoryStore"]
