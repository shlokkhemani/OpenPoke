"""Simplified agent roster management."""

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
    """View of execution agents derived from log files."""

    def __init__(self, roster_path: Path):
        self._roster_path = roster_path
        self._log_store = get_execution_agent_logs()
        self._entries: List[AgentRosterEntry] = []
        self.refresh()

    def refresh(self) -> None:
        """Refresh roster from disk or logs."""
        if self._roster_path.exists():
            try:
                data = json.loads(self._roster_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self._entries = [
                        AgentRosterEntry(
                            name=str(item.get("name", "")),
                            recent_actions=list(item.get("recent_actions", []))
                        )
                        for item in data
                        if isinstance(item, dict)
                    ]
                    return
            except Exception as exc:
                logger.warning("failed to load roster.json", extra={"error": str(exc)})

        self._entries = self._build_from_logs()
        self.persist()

    def _build_from_logs(self, limit: int = 5) -> List[AgentRosterEntry]:
        """Build roster from log files."""
        return [
            AgentRosterEntry(
                name=agent,
                recent_actions=[
                    f"{item['timestamp']} · {item['tag']}: {item['message']}"
                    for item in self._log_store.load_recent(agent, limit=limit)
                ]
            )
            for agent in self._log_store.list_agents()
        ]

    def persist(self) -> None:
        """Save roster to disk."""
        try:
            self._roster_path.parent.mkdir(parents=True, exist_ok=True)
            payload = [{"name": e.name, "recent_actions": e.recent_actions} for e in self._entries]
            self._roster_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("failed to persist roster.json", extra={"error": str(exc)})

    def get_roster(self) -> List[AgentRosterEntry]:
        """Get current roster entries."""
        return list(self._entries)


_settings = get_settings()
_agent_roster = AgentRoster(_settings.resolved_execution_agents_dir / "roster.json")


def get_agent_roster() -> AgentRoster:
    """Get the singleton roster instance."""
    return _agent_roster