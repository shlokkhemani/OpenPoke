from __future__ import annotations

from pathlib import Path

from ...config import get_settings
from .models import TriggerRecord
from .service import TriggerService
from .store import TriggerStore


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
