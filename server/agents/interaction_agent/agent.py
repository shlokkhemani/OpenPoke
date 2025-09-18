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


def prepare_openrouter_messages_experimental(
    latest_user_text: str,
) -> List[Dict[str, str]]:
    """Experimental: Return only the latest user message, letting system prompt handle history."""
    return [{"role": "user", "content": latest_user_text}]


def build_system_prompt(transcript: str) -> str:
    """Compose the system prompt used for the interaction agent."""
    sections = [SYSTEM_PROMPT]

    if transcript.strip():
        sections.extend(["<conversation_log>", transcript.strip(), "</conversation_log>"])

    sections.extend(["<active_agents>", _render_active_agents(), "</active_agents>"])

    return "\n\n".join(sections)


def _render_active_agents() -> str:
    """Render active agents for the system prompt."""
    roster = get_agent_roster()
    roster.refresh()
    entries = roster.get_roster()

    if not entries:
        return "None"

    rendered = []
    for entry in entries:
        name = escape(entry.name or "agent", quote=True)
        if entry.recent_actions:
            actions = "\n".join(
                f"<recent_action>{escape(action, quote=False)}</recent_action>"
                for action in entry.recent_actions
            )
            rendered.append(f'<agent name="{name}">\n{actions}\n</agent>')
        else:
            rendered.append(f'<agent name="{name}"></agent>')

    return "\n".join(rendered)