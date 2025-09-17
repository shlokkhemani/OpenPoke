from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _load_env_file() -> None:
    """Load server/.env if present (non-fatal)."""
    here = Path(__file__).parent
    env_path = here / ".env"
    if not env_path.is_file():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and value and key not in os.environ:
                os.environ[key] = value
    except Exception:
        # Optional env file load should never be fatal.
        pass


_load_env_file()


def _split_csv(raw: str) -> List[str]:
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items or ["*"]


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_name: str = Field(default=os.getenv("OPENPOKE_APP_NAME", "OpenPoke Server"))
    app_version: str = Field(default=os.getenv("OPENPOKE_VERSION", "0.3.0"))
    default_model: str = Field(default=os.getenv("OPENROUTER_MODEL", "openrouter/auto"))
    openrouter_api_key: Optional[str] = Field(default=os.getenv("OPENROUTER_API_KEY"))
    cors_allow_origins_raw: str = Field(default=os.getenv("OPENPOKE_CORS_ALLOW_ORIGINS", "*"))
    enable_docs: bool = Field(default=os.getenv("OPENPOKE_ENABLE_DOCS", "1") != "0")
    docs_url: Optional[str] = Field(default=os.getenv("OPENPOKE_DOCS_URL", "/docs"))
    composio_gmail_auth_config_id: Optional[str] = Field(default=os.getenv("COMPOSIO_GMAIL_AUTH_CONFIG_ID"))
    chat_history_path: Optional[str] = Field(default=os.getenv("OPENPOKE_CHAT_HISTORY_PATH"))

    @property
    def cors_allow_origins(self) -> List[str]:
        if self.cors_allow_origins_raw.strip() in {"", "*"}:
            return ["*"]
        return _split_csv(self.cors_allow_origins_raw)

    @property
    def resolved_docs_url(self) -> Optional[str]:
        if not self.enable_docs:
            return None
        return self.docs_url or "/docs"

    @property
    def resolved_chat_history_path(self) -> Path:
        raw = (self.chat_history_path or "").strip()
        if raw:
            path = Path(raw)
        else:
            path = Path(__file__).parent / "data" / "chat_history.json"
        if not path.is_absolute():
            path = (Path(__file__).parent / path).resolve()
        return path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
