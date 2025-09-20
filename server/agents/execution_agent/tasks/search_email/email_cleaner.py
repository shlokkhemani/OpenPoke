"""Backward-compatible re-export for shared email cleaning utilities."""

from server.services.gmail_processing import EmailTextCleaner

__all__ = ["EmailTextCleaner"]
