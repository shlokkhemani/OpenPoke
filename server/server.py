#!/usr/bin/env python3
"""CLI entrypoint for running the FastAPI app with Uvicorn."""

import argparse
import logging

import uvicorn

from .app import app
from .config import get_settings


def main() -> None:
    settings = get_settings()
    default_host = settings.server_host
    default_port = settings.server_port

    parser = argparse.ArgumentParser(description="OpenPoke FastAPI server")
    parser.add_argument("--host", default=default_host, help=f"Host to bind (default: {default_host})")
    parser.add_argument("--port", type=int, default=default_port, help=f"Port to bind (default: {default_port})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    # Reduce uvicorn access log noise - only show warnings and errors
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    # Reduce watchfiles noise during development
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    
    if args.reload:
        # For reload mode, use import string
        uvicorn.run(
            "server.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
            access_log=False,  # Disable access logs completely for cleaner output
        )
    else:
        # For production mode, use app object directly
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info",
            access_log=False,  # Disable access logs completely for cleaner output
        )


if __name__ == "__main__":  # pragma: no cover - CLI invocation guard
    main()
