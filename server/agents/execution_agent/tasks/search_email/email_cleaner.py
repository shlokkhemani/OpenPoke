"""Backward-compatible re-export for shared email cleaning utilities."""

from server.services.gmail import EmailTextCleaner

__all__ = ["EmailTextCleaner"]
