from __future__ import annotations

import threading
from html import escape, unescape
from pathlib import Path
from typing import Iterator, List, Optional, Protocol, Tuple

from ..config import get_settings
from ..logging_config import logger
from ..models import ChatMessage


class TranscriptFormatter(Protocol):
    def __call__(self, tag: str, payload: str) -> str:  # pragma: no cover - typing protocol
        ...


def _encode_payload(payload: str) -> str:
    normalized = payload.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = normalized.replace("\n", "\\n")
    return escape(collapsed, quote=False)


def _decode_payload(payload: str) -> str:
    return unescape(payload).replace("\\n", "\n")


def _default_formatter(tag: str, payload: str) -> str:
    encoded = _encode_payload(payload)
    return f"<{tag}>{encoded}</{tag}>\n"


class ConversationLog:
    """Append-only conversation log persisted to disk for the interaction agent."""

    def __init__(self, path: Path, formatter: TranscriptFormatter = _default_formatter):
        self._path = path
        self._formatter = formatter
        self._lock = threading.Lock()
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("conversation log directory creation failed", extra={"error": str(exc)})

    def _append(self, tag: str, payload: str) -> None:
        entry = self._formatter(tag, str(payload))
        with self._lock:
            try:
                with self._path.open("a", encoding="utf-8") as handle:
                    handle.write(entry)
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "conversation log append failed",
                    extra={"error": str(exc), "tag": tag, "path": str(self._path)},
                )
                raise

    def _parse_line(self, line: str) -> Optional[Tuple[str, str]]:
        stripped = line.strip()
        if not stripped.startswith("<") or "</" not in stripped:
            return None
        open_end = stripped.find(">")
        if open_end == -1:
            return None
        tag = stripped[1:open_end]
        close_start = stripped.rfind("</")
        close_end = stripped.rfind(">")
        if close_start == -1 or close_end == -1:
            return None
        closing_tag = stripped[close_start + 2 : close_end]
        if closing_tag != tag:
            return None
        payload = stripped[open_end + 1 : close_start]
        return tag, _decode_payload(payload)

    def iter_entries(self) -> Iterator[Tuple[str, str]]:
        with self._lock:
            try:
                lines = self._path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                lines = []
            except Exception as exc:  # pragma: no cover - defensive
                logger.error(
                    "conversation log read failed", extra={"error": str(exc), "path": str(self._path)}
                )
                raise
        for line in lines:
            item = self._parse_line(line)
            if item is not None:
                yield item

    def load_transcript(self) -> str:
        parts: List[str] = []
        for tag, payload in self.iter_entries():
            safe_payload = escape(payload, quote=False)
            parts.append(f"<{tag}>{safe_payload}</{tag}>")
        return "\n".join(parts)

    def record_user_message(self, content: str) -> None:
        self._append("user message", content)

    def record_agent_message(self, content: str) -> None:
        self._append("agent message", content)

    def record_reply(self, content: str) -> None:
        self._append("replies", content)

    def to_chat_messages(self) -> List[ChatMessage]:
        messages: List[ChatMessage] = []
        for tag, payload in self.iter_entries():
            if tag == "user message":
                messages.append(ChatMessage(role="user", content=payload))
            elif tag == "replies":
                messages.append(ChatMessage(role="assistant", content=payload))
        return messages

    def clear(self) -> None:
        with self._lock:
            try:
                if self._path.exists():
                    self._path.unlink()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "conversation log clear failed", extra={"error": str(exc), "path": str(self._path)}
                )
            finally:
                self._ensure_directory()


_conversation_log = ConversationLog(get_settings().resolved_conversation_log_path)


def get_conversation_log() -> ConversationLog:
    return _conversation_log


__all__ = ["ConversationLog", "get_conversation_log"]
