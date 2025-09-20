"""Persistence helper for tracking recently processed Gmail message IDs."""

from __future__ import annotations

import json
import threading
from collections import deque
from pathlib import Path
from typing import Deque, Iterable, List, Optional, Set

from ..logging_config import logger


class GmailSeenStore:
    """Maintain a bounded set of Gmail message IDs backed by a JSON file."""

    def __init__(self, path: Path, max_entries: int = 300) -> None:
        self._path = path
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: Deque[str] = deque()
        self._index: Set[str] = set()
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def has_entries(self) -> bool:
        with self._lock:
            return bool(self._entries)

    def is_seen(self, message_id: str) -> bool:
        normalized = self._normalize(message_id)
        if not normalized:
            return False
        with self._lock:
            return normalized in self._index

    def mark_seen(self, message_ids: Iterable[str]) -> None:
        normalized_ids = [mid for mid in (self._normalize(mid) for mid in message_ids) if mid]
        if not normalized_ids:
            return

        with self._lock:
            for message_id in normalized_ids:
                if message_id in self._index:
                    # Refresh recency by removing and re-appending
                    try:
                        self._entries.remove(message_id)
                    except ValueError:  # pragma: no cover - defensive
                        pass
                else:
                    self._index.add(message_id)
                self._entries.append(message_id)

            self._prune_locked()
            self._persist_locked()

    def snapshot(self) -> List[str]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._index.clear()
            self._persist_locked()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalize(self, message_id: Optional[str]) -> str:
        if not message_id:
            return ""
        return str(message_id).strip()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to load Gmail seen-store; starting empty",
                extra={"path": str(self._path), "error": str(exc)},
            )
            return

        if not isinstance(data, list):
            logger.warning(
                "Gmail seen-store payload invalid; expected list",
                extra={"path": str(self._path)},
            )
            return

        for raw_id in data[-self._max_entries :]:
            normalized = self._normalize(raw_id)
            if normalized and normalized not in self._index:
                self._entries.append(normalized)
                self._index.add(normalized)

    def _prune_locked(self) -> None:
        while len(self._entries) > self._max_entries:
            oldest = self._entries.popleft()
            self._index.discard(oldest)

    def _persist_locked(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = list(self._entries)
            self._path.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Failed to persist Gmail seen-store",
                extra={"path": str(self._path), "error": str(exc)},
            )


__all__ = ["GmailSeenStore"]
