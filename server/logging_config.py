from __future__ import annotations

import logging

logger = logging.getLogger("openpoke.server")


def configure_logging() -> None:
    if logger.handlers:
        return
    logging.basicConfig(level=logging.INFO)
