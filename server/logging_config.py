from __future__ import annotations

import logging
import os

logger = logging.getLogger("openpoke.server")


def configure_logging() -> None:
    """Configure logging with environment variable control."""
    if logger.handlers:
        return
    
    # Allow log level to be controlled via environment variable
    log_level = os.getenv("OPENPOKE_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    
    # Configure basic logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Reduce noise from common third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
