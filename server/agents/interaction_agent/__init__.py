"""Interaction agent module."""

from .agent import (
    build_system_prompt,
    prepare_openrouter_messages,
    prepare_openrouter_messages_experimental
)
from .tools import get_tool_schemas, handle_tool_call

MAX_OPENROUTER_MESSAGES = 12