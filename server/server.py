#!/usr/bin/env python3
"""CLI entrypoint for running the FastAPI app with Uvicorn."""

import argparse
import logging
import os

import uvicorn

from .app import app


def main() -> None:
    default_host = os.getenv("OPENPOKE_HOST", "0.0.0.0")
    try:
        default_port = int(os.getenv("OPENPOKE_PORT", "8001"))
    except ValueError:
        default_port = 8001

    parser = argparse.ArgumentParser(description="OpenPoke FastAPI server")
    parser.add_argument("--host", default=default_host, help=f"Host to bind (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to bind (default: {default_port})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    logging.getLogger("uvicorn").setLevel(logging.INFO)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":  # pragma: no cover - CLI invocation guard
    main()
