"""Internal Gmail utilities for the search_email task.

This module contains Gmail functions that are internal to the search_email task
and should not be exposed as public tools to execution agents.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from server.services.gmail import _load_gmail_user_id, execute_gmail_tool

# Schema for the internal LLM to call gmail_fetch_emails
GMAIL_FETCH_EMAILS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "gmail_fetch_emails",
        "description": "Search Gmail and retrieve matching messages",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail search query (same syntax as Gmail UI).",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of emails to return. Default: 10. Use higher values (20-50) only when absolutely necessary for comprehensive searches like 'all important emails this month'.",
                    "minimum": 1,
                    "maximum": 100,
                },
                "include_spam_trash": {
                    "type": "boolean",
                    "description": "Include spam and trash messages. Default: false.",
                },
            },
            "additionalProperties": False,
        },
    },
}


def gmail_fetch_emails(
    query: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    max_results: Optional[int] = None,
    page_token: Optional[str] = None,
    ids_only: Optional[bool] = None,
    include_payload: Optional[bool] = None,
    include_spam_trash: Optional[bool] = None,
    verbose: Optional[bool] = None,
) -> Dict[str, Any]:
    """Fetch Gmail messages with optional filters and verbosity controls.
    
    This is an internal function for the search_email task and should not
    be exposed as a public tool to execution agents.
    """
    arguments: Dict[str, Any] = {
        "query": query,
        "label_ids": label_ids,
        "max_results": max_results,
        "page_token": page_token,
        "ids_only": ids_only,
        "include_payload": include_payload,
        "include_spam_trash": include_spam_trash,
        "verbose": verbose,
    }
    composio_user_id = _load_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    
    # Use the same composio integration as the public tools
    return execute_gmail_tool("GMAIL_FETCH_EMAILS", composio_user_id, arguments)


__all__ = [
    "gmail_fetch_emails",
    "GMAIL_FETCH_EMAILS_SCHEMA",
]
