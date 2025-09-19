from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import json
from functools import partial

from ...services.execution_log import get_execution_agent_logs
from ...services.gmail import execute_gmail_tool, _load_gmail_user_id
from ...services.timezone_store import get_timezone_store
from ...services.triggers import TriggerRecord, get_trigger_service

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
    {
        "type": "function",
        "function": {
            "name": "createTrigger",
            "description": "Create a reminder trigger for the current execution agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payload": {
                        "type": "string",
                        "description": "Raw instruction text that should run when the trigger fires.",
                    },
                    "recurrence_rule": {
                        "type": "string",
                        "description": "iCalendar RRULE string describing how often to fire (optional).",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "ISO 8601 start time for the first firing. Defaults to now if omitted.",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name for interpreting the recurrence (defaults to UTC).",
                    },
                    "status": {
                        "type": "string",
                        "description": "Initial status; usually 'active' or 'paused'.",
                    },
                },
                "required": ["payload"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "updateTrigger",
            "description": "Update or pause an existing trigger owned by this execution agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "trigger_id": {
                        "type": "integer",
                        "description": "Identifier returned when the trigger was created.",
                    },
                    "payload": {
                        "type": "string",
                        "description": "Replace the instruction payload (optional).",
                    },
                    "recurrence_rule": {
                        "type": "string",
                        "description": "New RRULE definition (optional).",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "New ISO 8601 start time for the schedule (optional).",
                    },
                    "timezone": {
                        "type": "string",
                        "description": "Updated timezone identifier (optional).",
                    },
                    "status": {
                        "type": "string",
                        "description": "Set trigger status to 'active', 'paused', or 'completed'.",
                    },
                },
                "required": ["trigger_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listTriggers",
            "description": "List all triggers belonging to this execution agent.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
]
_LOG_STORE = get_execution_agent_logs()
_TRIGGER_SERVICE = get_trigger_service()


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


def _trigger_record_to_payload(record: TriggerRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "payload": record.payload,
        "start_time": record.start_time,
        "next_trigger": record.next_trigger,
        "recurrence_rule": record.recurrence_rule,
        "timezone": record.timezone,
        "status": record.status,
        "last_error": record.last_error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _create_trigger_tool(
    *,
    agent_name: str,
    payload: str,
    recurrence_rule: Optional[str] = None,
    start_time: Optional[str] = None,
    timezone: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    timezone_value = (timezone or "").strip() or get_timezone_store().get_timezone()
    summary_args = {
        "recurrence_rule": recurrence_rule,
        "start_time": start_time,
        "timezone": timezone_value,
        "status": status,
    }
    try:
        record = _TRIGGER_SERVICE.create_trigger(
            agent_name=agent_name,
            payload=payload,
            recurrence_rule=recurrence_rule,
            start_time=start_time,
            timezone_name=timezone_value,
            status=status,
        )
    except Exception as exc:  # pragma: no cover - defensive
        _LOG_STORE.record_action(
            agent_name,
            description=f"createTrigger failed | details={json.dumps(summary_args, ensure_ascii=False)} | error={exc}",
        )
        return {"error": str(exc)}

    _LOG_STORE.record_action(
        agent_name,
        description=f"createTrigger succeeded | trigger_id={record.id}",
    )
    return {
        "trigger_id": record.id,
        "status": record.status,
        "next_trigger": record.next_trigger,
        "start_time": record.start_time,
        "timezone": record.timezone,
        "recurrence_rule": record.recurrence_rule,
    }


def _update_trigger_tool(
    *,
    agent_name: str,
    trigger_id: Any,
    payload: Optional[str] = None,
    recurrence_rule: Optional[str] = None,
    start_time: Optional[str] = None,
    timezone: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        trigger_id_int = int(trigger_id)
    except (TypeError, ValueError):
        return {"error": "trigger_id must be an integer"}

    try:
        timezone_value = (timezone or "").strip() or None
        record = _TRIGGER_SERVICE.update_trigger(
            trigger_id_int,
            agent_name=agent_name,
            payload=payload,
            recurrence_rule=recurrence_rule,
            start_time=start_time,
            timezone_name=timezone_value,
            status=status,
        )
    except Exception as exc:  # pragma: no cover - defensive
        _LOG_STORE.record_action(
            agent_name,
            description=f"updateTrigger failed | id={trigger_id_int} | error={exc}",
        )
        return {"error": str(exc)}

    if record is None:
        return {"error": f"Trigger {trigger_id_int} not found"}

    _LOG_STORE.record_action(
        agent_name,
        description=f"updateTrigger succeeded | trigger_id={trigger_id_int}",
    )
    return {
        "trigger_id": record.id,
        "status": record.status,
        "next_trigger": record.next_trigger,
        "start_time": record.start_time,
        "timezone": record.timezone,
        "recurrence_rule": record.recurrence_rule,
        "last_error": record.last_error,
    }


def _list_triggers_tool(*, agent_name: str) -> Dict[str, Any]:
    try:
        records = _TRIGGER_SERVICE.list_triggers(agent_name=agent_name)
    except Exception as exc:  # pragma: no cover - defensive
        _LOG_STORE.record_action(
            agent_name,
            description=f"listTriggers failed | error={exc}",
        )
        return {"error": str(exc)}

    _LOG_STORE.record_action(
        agent_name,
        description=f"listTriggers succeeded | count={len(records)}",
    )
    return {"triggers": [_trigger_record_to_payload(record) for record in records]}


# Registry mapping tool names to Python callables.
BASE_TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "gmail_create_draft": gmail_create_draft,
    "gmail_execute_draft": gmail_execute_draft,
    "gmail_forward_email": gmail_forward_email,
    "gmail_reply_to_thread": gmail_reply_to_thread,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible tool schemas for the execution agent."""
    return TOOL_SCHEMAS


def get_tool_registry(agent_name: str) -> Dict[str, Callable[..., Any]]:
    """Return Python callables for executing tools by name."""
    registry = dict(BASE_TOOL_REGISTRY)
    registry.update(
        {
            "createTrigger": partial(_create_trigger_tool, agent_name=agent_name),
            "updateTrigger": partial(_update_trigger_tool, agent_name=agent_name),
            "listTriggers": partial(_list_triggers_tool, agent_name=agent_name),
        }
    )
    return registry
