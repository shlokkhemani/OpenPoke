from __future__ import annotations

from typing import Optional

from html import escape

from fastapi import status
from fastapi.responses import JSONResponse, PlainTextResponse

from ..config import Settings
from ..logging_config import logger
from ..models import ChatMessage, ChatRequest
from ..openrouter_client import OpenRouterError, stream_chat_completion
from ..prompts import get_interaction_system_prompt
from ..utils import error_response
from .agent_roster import get_agent_roster
from .conversation_log import get_conversation_log


def _extract_latest_user_message(payload: ChatRequest) -> Optional[ChatMessage]:
    for message in reversed(payload.messages):
        if message.role.lower().strip() == "user" and message.content.strip():
            return message
    return None


def _compose_system_prompt(base_prompt: str, transcript: str, active_agents: str) -> str:
    sections: list[str] = []

    if base_prompt.strip():
        sections.append(base_prompt.strip())

    cleaned_transcript = transcript.strip()
    if cleaned_transcript:
        sections.append("<conversation_log>")
        sections.append(cleaned_transcript)
        sections.append("</conversation_log>")

    sections.append("<active_agents>")
    sections.append(active_agents.strip() or "None")
    sections.append("</active_agents>")

    return "\n\n".join(sections)


def _format_active_agents_block() -> str:
    roster = get_agent_roster()
    roster.refresh()
    entries = roster.get_roster()
    if not entries:
        return "None"

    rendered: list[str] = []
    for entry in entries:
        name = escape(entry.name or "agent", quote=True)
        if entry.recent_actions:
            actions = "\n".join(
                f"<recent_action>{escape(action, quote=False)}</recent_action>" for action in entry.recent_actions
            )
            rendered.append(f"<agent name=\"{name}\">\n{actions}\n</agent>")
        else:
            rendered.append(f"<agent name=\"{name}\"></agent>")
    return "\n".join(rendered)


SEND_MESSAGE_TOOL: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "send_message_to_agent",
            "description": "Deliver instructions to a specific execution agent and await its action.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Execution agent identifier (e.g., 'gmail').",
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Actionable instructions for the execution agent.",
                    },
                },
                "required": ["agent_name", "instructions"],
                "additionalProperties": False,
            },
        },
    }
]

MAX_OPENROUTER_MESSAGES = 12


def _sanitize_messages(messages: list[ChatMessage], latest_user_text: str) -> list[dict[str, str]]:
    sanitized: list[dict[str, str]] = []
    for message in messages:
        role = (message.role or "").strip().lower()
        content = (message.content or "").strip()
        if role not in {"user", "assistant"}:
            continue
        if not content:
            continue
        sanitized.append({"role": role, "content": content})

    if not sanitized or sanitized[-1]["role"] != "user":
        sanitized.append({"role": "user", "content": latest_user_text})

    if len(sanitized) > MAX_OPENROUTER_MESSAGES:
        sanitized = sanitized[-MAX_OPENROUTER_MESSAGES:]

    return sanitized


def handle_chat_request(payload: ChatRequest, *, settings: Settings) -> PlainTextResponse | JSONResponse:
    conversation_log = get_conversation_log()

    user_message = _extract_latest_user_message(payload)
    if user_message is None:
        return error_response("Missing user message", status_code=status.HTTP_400_BAD_REQUEST)

    user_content = user_message.content.strip()
    if not user_content:
        return error_response("Empty user message", status_code=status.HTTP_400_BAD_REQUEST)

    conversation_log.record_user_message(user_content)
    transcript = conversation_log.load_transcript()

    base_system_prompt = (payload.system or "").strip() or get_interaction_system_prompt()
    active_agents_block = _format_active_agents_block()
    system_prompt = _compose_system_prompt(base_system_prompt, transcript, active_agents=active_agents_block)

    api_key = (payload.api_key or settings.openrouter_api_key or "").strip()
    if not api_key:
        return error_response("Missing api_key", status_code=status.HTTP_400_BAD_REQUEST)

    model_name = (payload.model or settings.default_model or "openrouter/auto").strip()

    openrouter_messages = _sanitize_messages(payload.messages, user_content)

    logger.info(
        "chat request",
        extra={
            "model": model_name,
            "message_length": len(user_content),
            "openrouter_messages": len(openrouter_messages),
        },
    )

    try:
        deltas = stream_chat_completion(
            model=model_name,
            messages=openrouter_messages,
            system=system_prompt,
            api_key=api_key,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            tools=SEND_MESSAGE_TOOL,
        )

        assistant_chunks: list[str] = []
        for delta in deltas:
            if delta.get("type") == "content":
                text = str(delta.get("text") or "")
                if text:
                    assistant_chunks.append(text)
    except OpenRouterError as exc:
        logger.warning("openrouter error", extra={"error": str(exc)})
        return error_response(str(exc), status_code=status.HTTP_502_BAD_GATEWAY)

    assistant_text = "".join(assistant_chunks).strip()

    if not assistant_text:
        return error_response("Assistant returned empty response", status_code=status.HTTP_502_BAD_GATEWAY)

    conversation_log.record_agent_message(assistant_text)
    conversation_log.record_reply(assistant_text)

    response_payload = ChatMessage(role="assistant", content=assistant_text)

    # Update log with assistant message already above; respond with plain text so the
    # Next.js proxy can stream or render the content without JSON parsing.
    return PlainTextResponse(response_payload.content)


__all__ = ["handle_chat_request"]
