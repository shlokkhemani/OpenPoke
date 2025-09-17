from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from ..config import get_settings
from ..logging_config import logger
from .execution_log import get_execution_agent_logs


@dataclass
class AgentRosterEntry:
    name: str
    recent_actions: List[str]


class AgentRoster:
    """Simple view of execution agents derived from log files."""

    def __init__(self, roster_path: Path):
        self._roster_path = roster_path
        self._log_store = get_execution_agent_logs()
        self._entries: List[AgentRosterEntry] = []
        self.refresh()

    def refresh(self) -> None:
        if self._roster_path.exists():
            try:
                data = json.loads(self._roster_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._entries = [
                        AgentRosterEntry(name=str(item.get("name", "")), recent_actions=list(item.get("recent_actions", [])))
                        for item in data
                        if isinstance(item, dict)
                    ]
                    return
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("failed to load roster.json", extra={"error": str(exc)})

        self._entries = self._build_from_logs()
        self.persist()

    def _build_from_logs(self, limit: int = 5) -> List[AgentRosterEntry]:
        entries: List[AgentRosterEntry] = []
        for agent in self._log_store.list_agents():
            recent = self._log_store.load_recent(agent, limit=limit)
            summary = [f"{item['timestamp']} · {item['tag']}: {item['message']}" for item in recent]
            entries.append(AgentRosterEntry(name=agent, recent_actions=summary))
        return entries

    def persist(self) -> None:
        payload = [
            {"name": entry.name, "recent_actions": entry.recent_actions}
            for entry in self._entries
        ]
        try:
            self._roster_path.parent.mkdir(parents=True, exist_ok=True)
            self._roster_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("failed to persist roster.json", extra={"error": str(exc)})

    def get_roster(self) -> List[AgentRosterEntry]:
        return list(self._entries)


_settings = get_settings()
_roster_file = _settings.resolved_execution_agents_dir / "roster.json"
_agent_roster = AgentRoster(_roster_file)


def get_agent_roster() -> AgentRoster:
    return _agent_roster


__all__ = ["AgentRosterEntry", "AgentRoster", "get_agent_roster"]
