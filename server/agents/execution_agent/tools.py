from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import json

from server.services.execution_log import get_execution_agent_logs
from server.services.gmail import execute_gmail_tool, _load_gmail_user_id

# OpenAI/OpenRouter-compatible tool schema list for the execution agent.
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "gmail_create_draft",
            "description": "Create a Gmail draft via Composio, supporting html/plain bodies, cc/bcc, and attachments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient_email": {
                        "type": "string",
                        "description": "Primary recipient email for the draft.",
                    },
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {
                        "type": "string",
                        "description": "Email body. Use HTML markup when is_html is true.",
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of CC recipient emails.",
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of BCC recipient emails.",
                    },
                    "extra_recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional recipients if the draft should include more addresses.",
                    },
                    "is_html": {
                        "type": "boolean",
                        "description": "Set true when the body contains HTML content.",
                    },
                    "thread_id": {
                        "type": "string",
                        "description": "Existing Gmail thread id if this draft belongs to a thread.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Override Gmail user id if not 'me'.",
                    },
                    "attachment": {
                        "type": "object",
                        "description": "Single attachment metadata (requires Composio-uploaded asset).",
                        "properties": {
                            "s3key": {"type": "string", "description": "S3 key of uploaded file."},
                            "name": {"type": "string", "description": "Attachment filename."},
                            "mimetype": {"type": "string", "description": "Attachment MIME type."},
                        },
                        "required": ["s3key", "name", "mimetype"],
                    },
                },
                "required": ["recipient_email", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_execute_draft",
            "description": "Send a previously created Gmail draft using Composio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "Identifier of the Gmail draft to send.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Override Gmail user id if not 'me'.",
                    },
                },
                "required": ["draft_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_forward_email",
            "description": "Forward an existing Gmail message with optional additional context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message id to forward.",
                    },
                    "recipient_email": {
                        "type": "string",
                        "description": "Email address to receive the forwarded message.",
                    },
                    "additional_text": {
                        "type": "string",
                        "description": "Optional text to prepend when forwarding.",
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Override Gmail user id if not 'me'.",
                    },
                },
                "required": ["message_id", "recipient_email"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_reply_to_thread",
            "description": "Send a reply within an existing Gmail thread via Composio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "Gmail thread id to reply to.",
                    },
                    "recipient_email": {
                        "type": "string",
                        "description": "Primary recipient for the reply (usually the original sender).",
                    },
                    "message_body": {
                        "type": "string",
                        "description": "Reply body. Use HTML markup when is_html is true.",
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of CC recipient emails.",
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of BCC recipient emails.",
                    },
                    "extra_recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional recipients if needed.",
                    },
                    "is_html": {
                        "type": "boolean",
                        "description": "Set true when the body contains HTML content.",
                    },
                    "attachment": {
                        "type": "object",
                        "description": "Single attachment metadata (requires Composio-uploaded asset).",
                        "properties": {
                            "s3key": {"type": "string", "description": "S3 key of uploaded file."},
                            "name": {"type": "string", "description": "Attachment filename."},
                            "mimetype": {"type": "string", "description": "Attachment MIME type."},
                        },
                        "required": ["s3key", "name", "mimetype"],
                    },
                    "user_id": {
                        "type": "string",
                        "description": "Override Gmail user id if not 'me'.",
                    },
                },
                "required": ["thread_id", "recipient_email", "message_body"],
                "additionalProperties": False,
            },
        },
    },
]
_LOG_STORE = get_execution_agent_logs()


def _execute(tool_name: str, composio_user_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Gmail tool and record the action for the execution agent journal."""
    # Don't use composio_user_id as agent_name - it's not an agent, it's a user ID
    agent_name = "gmail-execution-agent"
    payload = {k: v for k, v in arguments.items() if v is not None}
    payload_str = json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload else "{}"
    try:
        result = execute_gmail_tool(tool_name, composio_user_id, arguments=payload)
    except Exception as exc:
        _LOG_STORE.record_action(
            agent_name,
            description=f"{tool_name} failed | args={payload_str} | error={exc}",
        )
        raise

    _LOG_STORE.record_action(
        agent_name,
        description=f"{tool_name} succeeded | args={payload_str}",
    )
    return result


def gmail_create_draft(
    recipient_email: str,
    subject: str,
    body: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    extra_recipients: Optional[List[str]] = None,
    is_html: Optional[bool] = None,
    thread_id: Optional[str] = None,
    user_id: Optional[str] = None,
    attachment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    arguments: Dict[str, Any] = {
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
        "cc": cc,
        "bcc": bcc,
        "extra_recipients": extra_recipients,
        "is_html": is_html,
        "thread_id": thread_id,
        "user_id": user_id,
        "attachment": attachment,
    }
    composio_user_id = _load_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return _execute("GMAIL_CREATE_EMAIL_DRAFT", composio_user_id, arguments)


def gmail_execute_draft(
    draft_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    arguments = {"draft_id": draft_id, "user_id": user_id}
    composio_user_id = _load_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return _execute("GMAIL_SEND_DRAFT", composio_user_id, arguments)


def gmail_forward_email(
    message_id: str,
    recipient_email: str,
    additional_text: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    arguments = {
        "message_id": message_id,
        "recipient_email": recipient_email,
        "additional_text": additional_text,
        "user_id": user_id,
    }
    composio_user_id = _load_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return _execute("GMAIL_FORWARD_MESSAGE", composio_user_id, arguments)


def gmail_reply_to_thread(
    thread_id: str,
    recipient_email: str,
    message_body: str,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    extra_recipients: Optional[List[str]] = None,
    is_html: Optional[bool] = None,
    attachment: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    arguments = {
        "thread_id": thread_id,
        "recipient_email": recipient_email,
        "message_body": message_body,
        "cc": cc,
        "bcc": bcc,
        "extra_recipients": extra_recipients,
        "is_html": is_html,
        "attachment": attachment,
        "user_id": user_id,
    }
    composio_user_id = _load_gmail_user_id()
    if not composio_user_id:
        return {"error": "Gmail not connected. Please connect Gmail in settings first."}
    return _execute("GMAIL_REPLY_TO_THREAD", composio_user_id, arguments)


# Registry mapping tool names to Python callables.
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "gmail_create_draft": gmail_create_draft,
    "gmail_execute_draft": gmail_execute_draft,
    "gmail_forward_email": gmail_forward_email,
    "gmail_reply_to_thread": gmail_reply_to_thread,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible tool schemas for the execution agent."""
    return TOOL_SCHEMAS


def get_tool_registry() -> Dict[str, Callable[..., Any]]:
    """Return Python callables for executing tools by name."""
    return TOOL_REGISTRY
