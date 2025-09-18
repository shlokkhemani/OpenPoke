"""Tool definitions for interaction agent."""

import json
from typing import Any, Callable, Dict, List, Optional

from ...logging_config import logger
from ...services.execution_log import get_execution_agent_logs

# Tool schemas for OpenRouter
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "send_message_to_agent",
            "description": "Deliver instructions to a specific execution agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Agent identifier (e.g., 'gmail')."},
                    "instructions": {"type": "string", "description": "Instructions for the agent."},
                },
                "required": ["agent_name", "instructions"],
                "additionalProperties": False,
            },
        },
    },
]


def send_message_to_agent(agent_name: str, instructions: str) -> str:
    """Send instructions to an execution agent."""
    log_store = get_execution_agent_logs()
    log_store.record_request(agent_name, instructions)
    logger.info(f"queued for agent: {agent_name}")
    return f"Queued instructions for agent '{agent_name}'."


# Registry mapping tool names to Python callables
TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "send_message_to_agent": send_message_to_agent,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return OpenAI-compatible tool schemas."""
    return TOOL_SCHEMAS


def get_tool_registry() -> Dict[str, Callable[..., Any]]:
    """Return Python callables for executing tools by name."""
    return TOOL_REGISTRY


def handle_tool_call(name: str, arguments: Any) -> Optional[str]:
    """Handle tool calls from interaction agent."""
    tool_func = TOOL_REGISTRY.get(name)
    if not tool_func:
        logger.warning(f"unexpected tool: {name}")
        return None

    try:
        # Parse arguments if string
        if isinstance(arguments, str):
            args = json.loads(arguments) if arguments.strip() else {}
        elif isinstance(arguments, dict):
            args = arguments
        else:
            return "Invalid arguments format"

        # Execute tool
        return tool_func(**args)
    except json.JSONDecodeError:
        return "Invalid JSON"
    except TypeError as e:
        return f"Missing required arguments: {e}"
    except Exception as e:
        logger.error(f"tool call failed: {e}")
        return "Failed to execute"