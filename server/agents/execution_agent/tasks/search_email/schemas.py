"""Schemas for the email search task tools."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

TASK_TOOL_NAME = "task_email_search"
SEARCH_TOOL_NAME = "gmail_fetch_emails"
COMPLETE_TOOL_NAME = "return_search_results"

_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": TASK_TOOL_NAME,
            "description": "Expand a raw Gmail search request into multiple targeted queries and return relevant emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_query": {
                        "type": "string",
                        "description": "Raw search request describing the emails to find.",
                    },
                },
                "required": ["search_query"],
                "additionalProperties": False,
            },
        },
    }
]


class GmailSearchEmail(BaseModel):
    """Normalized representation of an email returned from Composio."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    thread_id: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    timestamp: Optional[datetime] = None
    label_ids: List[str] = Field(default_factory=list)
    preview_subject: Optional[str] = None
    preview_body: Optional[str] = None
    query: str


class EmailSearchToolResult(BaseModel):
    """Structured payload for each tool-call response."""

    status: Literal["success", "error"]
    query: Optional[str] = None
    result_count: Optional[int] = None
    next_page_token: Optional[str] = None
    messages: List[GmailSearchEmail] = Field(default_factory=list)
    error: Optional[str] = None


class TaskEmailSearchPayload(BaseModel):
    """Envelope for the final email selection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    emails: List[GmailSearchEmail]


_COMPLETION_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": COMPLETE_TOOL_NAME,
            "description": "Return the final list of relevant Gmail message ids that match the search criteria.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_ids": {
                        "type": "array",
                        "description": "List of Gmail message ids deemed relevant.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["message_ids"],
                "additionalProperties": False,
            },
        },
    }
]

# Global cache for the modified Gmail fetch schema
_GMAIL_FETCH_SCHEMA: Optional[Dict[str, Any]] = None


def get_completion_schema() -> Dict[str, Any]:
    return _COMPLETION_SCHEMAS[0]


def get_schemas() -> List[Dict[str, Any]]:
    """Return the JSON schema for the email search task."""

    return _SCHEMAS


def get_gmail_fetch_schema() -> Dict[str, Any]:
    """Get Gmail fetch schema with max_results parameter removed for LLM use."""
    global _GMAIL_FETCH_SCHEMA
    if _GMAIL_FETCH_SCHEMA is None:
        from ...tools import gmail
        original = _resolve_gmail_fetch_schema(gmail.get_schemas())
        sanitized = deepcopy(original)
        try:
            properties = sanitized["function"]["parameters"]["properties"]
        except KeyError:
            properties = None
        if isinstance(properties, dict):
            properties.pop("max_results", None)
        _GMAIL_FETCH_SCHEMA = sanitized
    return _GMAIL_FETCH_SCHEMA


def _resolve_gmail_fetch_schema(schemas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Find the gmail_fetch_emails schema from the provided schemas."""
    for schema in schemas:
        function = schema.get("function", {})
        if function.get("name") == SEARCH_TOOL_NAME:
            return schema
    raise RuntimeError("gmail_fetch_emails schema unavailable for task_email_search")


__all__ = [
    "GmailSearchEmail",
    "EmailSearchToolResult",
    "TaskEmailSearchPayload",
    "SEARCH_TOOL_NAME",
    "COMPLETE_TOOL_NAME",
    "TASK_TOOL_NAME",
    "get_completion_schema",
    "get_schemas",
    "get_gmail_fetch_schema",
]
