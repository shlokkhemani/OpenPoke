from __future__ import annotations

import logging

logger = logging.getLogger("openpoke.server")


def configure_logging() -> None:
    """Configure logging with a fixed log level."""
    if logger.handlers:
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
