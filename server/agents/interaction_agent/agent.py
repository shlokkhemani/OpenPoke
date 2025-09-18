"""Core interaction agent functionality."""

from html import escape
from pathlib import Path
from typing import Dict, List, Optional

from ...models import ChatMessage
from ...services.agent_roster import get_agent_roster

MAX_OPENROUTER_MESSAGES = 12

# Load system prompt from file
_prompt_path = Path(__file__).parent / "system_prompt.md"
SYSTEM_PROMPT = _prompt_path.read_text(encoding="utf-8").strip()


def prepare_openrouter_messages(
    history: List[ChatMessage],
    latest_user_text: str,
    *,
    max_messages: int = MAX_OPENROUTER_MESSAGES,
) -> List[Dict[str, str]]:
    """Convert chat history into OpenRouter-compatible messages with bounds."""
    sanitized = [
        {"role": msg.role.strip().lower(), "content": msg.content.strip()}
        for msg in history
        if msg.role.strip().lower() in {"user", "assistant"} and msg.content.strip()
    ]

    if not sanitized or sanitized[-1]["role"] != "user":
        sanitized.append({"role": "user", "content": latest_user_text})

    return sanitized[-max_messages:] if max_messages > 0 else sanitized


def prepare_message_with_history(
    latest_user_text: str,
    transcript: str,
    message_type: str = "user"
) -> List[Dict[str, str]]:
    """
    Prepare a single user message that includes conversation history as tags.

    Args:
        latest_user_text: The new message content
        transcript: Previous conversation history
        message_type: "user" or "agent" to label the new message appropriately
    """
    if transcript.strip():
        # Include history as tags before the new message
        if message_type == "agent":
            content = f"<conversation_history>\n{transcript}\n</conversation_history>\n\n<new_agent_message>\n{latest_user_text}\n</new_agent_message>"
        else:
            content = f"<conversation_history>\n{transcript}\n</conversation_history>\n\n<new_user_message>\n{latest_user_text}\n</new_user_message>"
    else:
        # No history, just wrap the new message
        if message_type == "agent":
            content = f"<new_agent_message>\n{latest_user_text}\n</new_agent_message>"
        else:
            content = f"<new_user_message>\n{latest_user_text}\n</new_user_message>"

    return [{"role": "user", "content": content}]


def build_system_prompt() -> str:
    """Compose the system prompt used for the interaction agent."""
    sections = [SYSTEM_PROMPT]
    sections.extend(["<active_agents>", _render_active_agents(), "</active_agents>"])
    return "\n\n".join(sections)


def _render_active_agents() -> str:
    """Render active agents for the system prompt."""
    roster = get_agent_roster()
    roster.load()  # Reload from disk to get latest agents
    agents = roster.get_agents()

    if not agents:
        return "None"

    # Simple list of agent names
    rendered = []
    for agent_name in agents:
        name = escape(agent_name or "agent", quote=True)
        rendered.append(f'<agent name="{name}"></agent>')

    return "\n".join(rendered)