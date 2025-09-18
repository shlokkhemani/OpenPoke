"""Simplified configuration management."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


def _load_env_file() -> None:
    """Load .env from root directory if present."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.is_file():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, value = stripped.split("=", 1)
                key, value = key.strip(), value.strip().strip("'\"")
                if key and value and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


_load_env_file()


class Settings(BaseModel):
    """Application settings with simplified path resolution."""

    app_name: str = Field(default=os.getenv("OPENPOKE_APP_NAME", "OpenPoke Server"))
    app_version: str = Field(default=os.getenv("OPENPOKE_VERSION", "0.3.0"))
    default_model: str = Field(default=os.getenv("OPENROUTER_MODEL", "openrouter/auto"))
    openrouter_api_key: Optional[str] = Field(default=os.getenv("OPENROUTER_API_KEY"))
    cors_allow_origins_raw: str = Field(default=os.getenv("OPENPOKE_CORS_ALLOW_ORIGINS", "*"))
    enable_docs: bool = Field(default=os.getenv("OPENPOKE_ENABLE_DOCS", "1") != "0")
    docs_url: Optional[str] = Field(default=os.getenv("OPENPOKE_DOCS_URL", "/docs"))
    composio_gmail_auth_config_id: Optional[str] = Field(default=os.getenv("COMPOSIO_GMAIL_AUTH_CONFIG_ID"))

    # Path configurations - simplified
    chat_history_path: Optional[str] = Field(default=os.getenv("OPENPOKE_CHAT_HISTORY_PATH"))
    conversation_log_path: Optional[str] = Field(default=os.getenv("OPENPOKE_CONVERSATION_LOG_PATH"))
    execution_agents_dir: Optional[str] = Field(default=os.getenv("OPENPOKE_EXECUTION_AGENTS_DIR"))

    @property
    def cors_allow_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_allow_origins_raw.strip() in {"", "*"}:
            return ["*"]
        return [origin.strip() for origin in self.cors_allow_origins_raw.split(",") if origin.strip()]

    @property
    def resolved_docs_url(self) -> Optional[str]:
        """Get docs URL if enabled."""
        return (self.docs_url or "/docs") if self.enable_docs else None

    def resolve_path(self, raw_path: Optional[str], default: Path) -> Path:
        """Helper to resolve paths consistently."""
        if raw_path and raw_path.strip():
            path = Path(raw_path.strip())
            return path if path.is_absolute() else (Path(__file__).parent / path).resolve()
        return default

    @property
    def resolved_conversation_log_path(self) -> Path:
        """Get conversation log path."""
        return self.resolve_path(
            self.conversation_log_path or self.chat_history_path,
            Path(__file__).parent / "data" / "conversation" / "poke_conversation.log"
        )

    @property
    def resolved_chat_history_path(self) -> Path:
        """Alias for conversation log path."""
        return self.resolved_conversation_log_path

    @property
    def resolved_execution_agents_dir(self) -> Path:
        """Get execution agents directory."""
        return self.resolve_path(
            self.execution_agents_dir,
            Path(__file__).parent / "data" / "execution_agents"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()