"""Trigger storage and scheduling utilities."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dateutil import parser as date_parser
from dateutil.rrule import rrulestr
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..logging_config import logger


UTC = timezone.utc
DEFAULT_STATUS = "active"
VALID_STATUSES = {"active", "paused", "completed"}


@dataclass
class TriggerRecord:
    """Serialized trigger representation returned to callers."""

    id: int
    agent_name: str
    payload: str
    start_time: Optional[str]
    next_trigger: Optional[str]
    recurrence_rule: Optional[str]
    timezone: Optional[str]
    status: str
    last_error: Optional[str]
    created_at: str
    updated_at: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _to_storage_timestamp(moment: datetime) -> str:
    """Normalize timestamps before writing to SQLite."""
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class TriggerStore:
    """Low-level persistence for triggers backed by SQLite."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._ensure_directory()
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_directory(self) -> None:
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("trigger directory creation failed", extra={"error": str(exc)})

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        schema_sql = """
        CREATE TABLE IF NOT EXISTS triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            payload TEXT NOT NULL,
            start_time TEXT,
            next_trigger TEXT,
            recurrence_rule TEXT,
            timezone TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_triggers_agent_next
        ON triggers (agent_name, next_trigger);
        """
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(schema_sql)
            conn.execute(index_sql)

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------
    def insert(self, payload: Dict[str, Any]) -> int:
        with self._lock, self._connect() as conn:
            columns = ", ".join(payload.keys())
            placeholders = ", ".join([":" + key for key in payload.keys()])
            sql = f"INSERT INTO triggers ({columns}) VALUES ({placeholders})"
            conn.execute(sql, payload)
            trigger_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return int(trigger_id)

    def fetch_one(self, trigger_id: int, agent_name: str) -> Optional[TriggerRecord]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM triggers WHERE id = ? AND agent_name = ?",
                (trigger_id, agent_name),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def update(self, trigger_id: int, agent_name: str, fields: Dict[str, Any]) -> bool:
        if not fields:
            return False
        assignments = ", ".join(f"{key} = :{key}" for key in fields.keys())
        sql = (
            f"UPDATE triggers SET {assignments}, updated_at = :updated_at"
            " WHERE id = :trigger_id AND agent_name = :agent_name"
        )
        payload = {
            **fields,
            "updated_at": _to_storage_timestamp(_utc_now()),
            "trigger_id": trigger_id,
            "agent_name": agent_name,
        }
        with self._lock, self._connect() as conn:
            cursor = conn.execute(sql, payload)
            return cursor.rowcount > 0

    def list_for_agent(self, agent_name: str) -> List[TriggerRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM triggers WHERE agent_name = ? ORDER BY next_trigger IS NULL, next_trigger",
                (agent_name,),
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def fetch_due(self, agent_name: Optional[str], before_iso: str) -> List[TriggerRecord]:
        sql = (
            "SELECT * FROM triggers WHERE status = 'active' AND next_trigger IS NOT NULL"
            " AND next_trigger <= ?"
        )
        params: List[Any] = [before_iso]
        if agent_name:
            sql += " AND agent_name = ?"
            params.append(agent_name)
        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def clear_all(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM triggers")

    def _row_to_record(self, row: sqlite3.Row) -> TriggerRecord:
        return TriggerRecord(
            id=row["id"],
            agent_name=row["agent_name"],
            payload=row["payload"],
            start_time=row["start_time"],
            next_trigger=row["next_trigger"],
            recurrence_rule=row["recurrence_rule"],
            timezone=row["timezone"],
            status=row["status"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class TriggerService:
    """High-level trigger management with recurrence awareness."""

    def __init__(self, store: TriggerStore):
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create_trigger(
        self,
        *,
        agent_name: str,
        payload: str,
        recurrence_rule: Optional[str] = None,
        start_time: Optional[str] = None,
        timezone_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> TriggerRecord:
        tz = self._resolve_timezone(timezone_name)
        now = _utc_now()
        start_dt_local = self._coerce_start_datetime(start_time, tz, now)
        next_fire = self._compute_next_fire(
            recurrence_rule=recurrence_rule,
            start_dt_local=start_dt_local,
            tz=tz,
            now=now,
        )
        stored_recurrence = self._build_recurrence(recurrence_rule, start_dt_local, tz)
        timestamp = _to_storage_timestamp(now)
        record: Dict[str, Any] = {
            "agent_name": agent_name,
            "payload": payload,
            "start_time": _to_storage_timestamp(start_dt_local.astimezone(UTC)),
            "next_trigger": _to_storage_timestamp(next_fire) if next_fire else None,
            "recurrence_rule": stored_recurrence,
            "timezone": tz.key if hasattr(tz, "key") else "UTC",
            "status": self._normalize_status(status),
            "last_error": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        trigger_id = self._store.insert(record)
        created = self._store.fetch_one(trigger_id, agent_name)
        if not created:  # pragma: no cover - defensive
            raise RuntimeError("Failed to load trigger after insert")
        return created

    def update_trigger(
        self,
        trigger_id: int,
        *,
        agent_name: str,
        payload: Optional[str] = None,
        recurrence_rule: Optional[str] = None,
        start_time: Optional[str] = None,
        timezone_name: Optional[str] = None,
        status: Optional[str] = None,
        last_error: Optional[str] = None,
        clear_error: bool = False,
    ) -> Optional[TriggerRecord]:
        existing = self._store.fetch_one(trigger_id, agent_name)
        if existing is None:
            return None

        tz = self._resolve_timezone(timezone_name or existing.timezone)
        start_dt_local = self._coerce_start_datetime(
            start_time,
            tz,
            self._parse_iso(existing.start_time) if existing.start_time else _utc_now(),
        )

        fields: Dict[str, Any] = {}
        if payload is not None:
            fields["payload"] = payload
        if status is not None:
            fields["status"] = self._normalize_status(status)
        if start_time is not None:
            fields["start_time"] = _to_storage_timestamp(start_dt_local.astimezone(UTC))
        if timezone_name is not None:
            fields["timezone"] = tz.key if hasattr(tz, "key") else "UTC"

        recurrence_to_use = recurrence_rule if recurrence_rule is not None else existing.recurrence_rule
        if recurrence_rule is not None or start_time is not None or timezone_name is not None:
            next_fire = self._compute_next_fire(
                recurrence_rule=recurrence_to_use,
                start_dt_local=start_dt_local,
                tz=tz,
                now=_utc_now(),
            )
            fields["next_trigger"] = _to_storage_timestamp(next_fire) if next_fire else None
            fields["recurrence_rule"] = self._build_recurrence(recurrence_to_use, start_dt_local, tz)

        if clear_error:
            fields["last_error"] = None
        elif last_error is not None:
            fields["last_error"] = last_error

        if not fields:
            return existing

        updated = self._store.update(trigger_id, agent_name, fields)
        return self._store.fetch_one(trigger_id, agent_name) if updated else existing

    def list_triggers(self, *, agent_name: str) -> List[TriggerRecord]:
        return self._store.list_for_agent(agent_name)

    def get_due_triggers(self, *, before: datetime, agent_name: Optional[str] = None) -> List[TriggerRecord]:
        iso_cutoff = _to_storage_timestamp(before)
        return self._store.fetch_due(agent_name, iso_cutoff)

    def mark_as_completed(self, trigger_id: int, *, agent_name: str) -> None:
        self._store.update(
            trigger_id,
            agent_name,
            {
                "status": "completed",
                "next_trigger": None,
                "last_error": None,
            },
        )

    def schedule_next_occurrence(
        self,
        trigger: TriggerRecord,
        *,
        fired_at: datetime,
    ) -> Optional[TriggerRecord]:
        if not trigger.recurrence_rule:
            self.mark_as_completed(trigger.id, agent_name=trigger.agent_name)
            return self._store.fetch_one(trigger.id, trigger.agent_name)

        tz = self._resolve_timezone(trigger.timezone)
        next_fire = self._compute_next_after(trigger.recurrence_rule, fired_at, tz)
        fields: Dict[str, Any] = {
            "next_trigger": _to_storage_timestamp(next_fire) if next_fire else None,
            "last_error": None,
        }
        if next_fire is None:
            fields["status"] = "completed"
        self._store.update(trigger.id, trigger.agent_name, fields)
        return self._store.fetch_one(trigger.id, trigger.agent_name)

    def record_failure(self, trigger: TriggerRecord, error: str) -> None:
        self._store.update(
            trigger.id,
            trigger.agent_name,
            {
                "last_error": error,
            },
        )

    def clear_next_fire(self, trigger_id: int, *, agent_name: str) -> Optional[TriggerRecord]:
        self._store.update(
            trigger_id,
            agent_name,
            {
                "next_trigger": None,
            },
        )
        return self._store.fetch_one(trigger_id, agent_name)

    def clear_all(self) -> None:
        self._store.clear_all()

    # ------------------------------------------------------------------
    # Recurrence helpers
    # ------------------------------------------------------------------
    def _compute_next_fire(
        self,
        *,
        recurrence_rule: Optional[str],
        start_dt_local: datetime,
        tz: ZoneInfo,
        now: datetime,
    ) -> Optional[datetime]:
        if recurrence_rule:
            rule = rrulestr(self._build_recurrence(recurrence_rule, start_dt_local, tz))
            next_occurrence = rule.after(now.astimezone(tz), inc=True)
            if next_occurrence is None:
                return None
            if next_occurrence.tzinfo is None:
                next_occurrence = next_occurrence.replace(tzinfo=tz)
            return next_occurrence.astimezone(UTC)

        if start_dt_local < now.astimezone(tz):
            logger.warning(
                "start_time in the past; trigger will fire immediately",
                extra={"start_time": start_dt_local.isoformat()},
            )
        return start_dt_local.astimezone(UTC)

    def _compute_next_after(self, stored_recurrence: str, fired_at: datetime, tz: ZoneInfo) -> Optional[datetime]:
        rule = rrulestr(stored_recurrence)
        next_occurrence = rule.after(fired_at.astimezone(tz), inc=False)
        if next_occurrence is None:
            return None
        if next_occurrence.tzinfo is None:
            next_occurrence = next_occurrence.replace(tzinfo=tz)
        return next_occurrence.astimezone(UTC)

    def _build_recurrence(
        self,
        recurrence_rule: Optional[str],
        start_dt_local: datetime,
        tz: ZoneInfo,
    ) -> Optional[str]:
        if not recurrence_rule:
            return None

        if start_dt_local.tzinfo is None:
            start_dt_local = start_dt_local.replace(tzinfo=tz)
        else:
            start_dt_local = start_dt_local.astimezone(tz)

        if start_dt_local.utcoffset() == timedelta(0):
            dt_line = f"DTSTART:{start_dt_local.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        else:
            tz_name = getattr(tz, "key", "UTC")
            dt_line = f"DTSTART;TZID={tz_name}:{start_dt_local.strftime('%Y%m%dT%H%M%S')}"

        lines = [segment.strip() for segment in recurrence_rule.strip().splitlines() if segment.strip()]
        filtered = [segment for segment in lines if not segment.upper().startswith("DTSTART")]
        if not filtered:
            raise ValueError("recurrence_rule must contain an RRULE definition")

        if not filtered[0].upper().startswith("RRULE"):
            filtered[0] = f"RRULE:{filtered[0]}"

        return "\n".join([dt_line, *filtered])

    def _coerce_start_datetime(self, start_time: Optional[str], tz: ZoneInfo, fallback: datetime) -> datetime:
        if start_time:
            return self._parse_datetime(start_time, tz)
        return fallback.astimezone(tz)

    def _parse_datetime(self, timestamp: str, tz: ZoneInfo) -> datetime:
        dt = date_parser.isoparse(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        else:
            dt = dt.astimezone(tz)
        return dt

    def _parse_iso(self, timestamp: str) -> datetime:
        dt = date_parser.isoparse(timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt

    def _resolve_timezone(self, timezone_name: Optional[str]) -> ZoneInfo:
        if timezone_name:
            try:
                return ZoneInfo(timezone_name)
            except Exception:
                logger.warning(
                    "unknown timezone provided; defaulting to UTC",
                    extra={"timezone": timezone_name},
                )
        return ZoneInfo("UTC")

    def _normalize_status(self, status: Optional[str]) -> str:
        if not status:
            return DEFAULT_STATUS
        normalized = status.lower()
        if normalized not in VALID_STATUSES:
            logger.warning("invalid status supplied; defaulting to active", extra={"status": status})
            return DEFAULT_STATUS
        return normalized


_settings = get_settings()
_default_db_path = _settings.resolve_path(
    None,
    Path(__file__).parent.parent / "data" / "triggers.db",
)
_trigger_store = TriggerStore(_default_db_path)
_trigger_service = TriggerService(_trigger_store)


def get_trigger_service() -> TriggerService:
    return _trigger_service


__all__ = [
    "TriggerRecord",
    "TriggerService",
    "get_trigger_service",
]
