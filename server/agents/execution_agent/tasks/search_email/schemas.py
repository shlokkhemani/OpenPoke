"""Schemas for the email search task tools."""

from __future__ import annotations

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
    """Clean email representation with enhanced content processing."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    # Core identifiers
    id: str  # message_id from Gmail API
    thread_id: Optional[str] = None
    query: str  # The search query that found this email
    
    # Email metadata
    subject: str
    sender: str
    recipient: str  # to field
    timestamp: datetime
    label_ids: List[str] = Field(default_factory=list)
    
    # Clean content (primary field for LLM consumption)
    clean_text: str  # Processed, readable email content
    
    # Attachment information
    has_attachments: bool = False
    attachment_count: int = 0
    attachment_filenames: List[str] = Field(default_factory=list)


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

def get_completion_schema() -> Dict[str, Any]:
    return _COMPLETION_SCHEMAS[0]


def get_schemas() -> List[Dict[str, Any]]:
    """Return the JSON schema for the email search task."""

    return _SCHEMAS


__all__ = [
    "GmailSearchEmail",
    "EmailSearchToolResult",
    "TaskEmailSearchPayload",
    "SEARCH_TOOL_NAME",
    "COMPLETE_TOOL_NAME",
    "TASK_TOOL_NAME",
    "get_completion_schema",
    "get_schemas",
]
