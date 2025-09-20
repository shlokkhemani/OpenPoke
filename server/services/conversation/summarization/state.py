from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class LogEntry:
    """Snapshot of a single conversation log entry."""

    tag: str
    payload: str
    index: int = -1
    timestamp: Optional[str] = None


@dataclass
class SummaryState:
    """Persisted working-memory summary state."""

    summary_text: str = ""
    last_index: int = -1
    updated_at: Optional[datetime] = None
    unsummarized_entries: List[LogEntry] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "SummaryState":
        return cls()


__all__ = ["LogEntry", "SummaryState"]
