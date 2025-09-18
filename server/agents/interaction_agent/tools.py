"""Tool definitions for interaction agent."""

import json
import uuid
from typing import Any, Dict, List, Optional

from ...logging_config import logger
from ...services.agent_roster import get_agent_roster
from ...services.conversation_log import get_conversation_log
from ...services.execution_log import get_execution_agent_logs

# Tool schemas for OpenRouter
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "send_message_to_agent",
            "description": "Deliver instructions to a specific execution agent. Creates a new agent if the name doesn't exist in the roster, or reuses an existing one.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Human-readable agent name describing its purpose (e.g., 'Vercel Job Offer', 'Email to Sharanjeet'). This name will be used to identify and potentially reuse the agent."
                    },
                    "instructions": {"type": "string", "description": "Instructions for the agent to execute."},
                },
                "required": ["agent_name", "instructions"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_draft",
            "description": "Record an email draft so the user can review the exact text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email for the draft.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject for the draft.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content (plain text).",
                    },
                },
                "required": ["to", "subject", "body"],
                "additionalProperties": False,
            },
        },
    },
]

# Track pending execution requests
_pending_executions = {}


def send_message_to_agent(agent_name: str, instructions: str) -> str:
    """Send instructions to an execution agent."""
    request_id = str(uuid.uuid4())

    roster = get_agent_roster()
    roster.load()
    existing_agents = set(roster.get_agents())
    is_new = agent_name not in existing_agents

    get_execution_agent_logs().record_request(agent_name, instructions)

    _pending_executions[request_id] = {
        "agent_name": agent_name,
        "instructions": instructions,
        "is_new": is_new
    }

    action = "Creating new" if is_new else "Reusing existing"
    logger.info(f"{action} agent: {agent_name} (request_id: {request_id})")

    return f"{action} agent '{agent_name}'. Request ID: {request_id}"


def send_draft(
    to: str,
    subject: str,
    body: str,
) -> Optional[str]:
    """Record a draft update in the conversation log for the interaction agent."""

    log = get_conversation_log()

    lines = [
        "<draft>",
        f"To: {to}",
        f"Subject: {subject}",
        "",
        body,
        "</draft>",
    ]

    message = "\n".join(lines)

    log.record_draft(message)
    logger.info(
        "recorded draft",
        extra={
            "recipient": to,
            "subject": subject,
        },
    )

    return None


TOOL_REGISTRY = {
    "send_message_to_agent": send_message_to_agent,
    "send_draft": send_draft,
}


def get_tool_schemas():
    """Return OpenAI-compatible tool schemas."""
    return TOOL_SCHEMAS


def get_tool_registry():
    """Return Python callables for executing tools by name."""
    return TOOL_REGISTRY


def handle_tool_call(name: str, arguments: Any) -> Optional[str]:
    """Handle tool calls from interaction agent."""
    tool_func = TOOL_REGISTRY.get(name)
    if not tool_func:
        logger.warning(f"unexpected tool: {name}")
        return None

    try:
        if isinstance(arguments, str):
            args = json.loads(arguments) if arguments.strip() else {}
        elif isinstance(arguments, dict):
            args = arguments
        else:
            return "Invalid arguments format"
        return tool_func(**args)
    except json.JSONDecodeError:
        return "Invalid JSON"
    except TypeError as e:
        return f"Missing required arguments: {e}"
    except Exception as e:
        logger.error(f"tool call failed: {e}")
        return "Failed to execute"
