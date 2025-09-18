from __future__ import annotations

from typing import Optional

from fastapi import status
from fastapi.responses import JSONResponse, PlainTextResponse

from ..agents.interaction_agent import (
    build_system_prompt,
    get_tool_schemas,
    handle_tool_call,
    prepare_openrouter_messages,
    prepare_openrouter_messages_experimental,
)
from ..config import Settings
from ..logging_config import logger
from ..models import ChatMessage, ChatRequest
from ..openrouter_client import OpenRouterError, request_chat_completion
from ..utils import error_response
from .conversation_log import get_conversation_log


def _extract_latest_user_message(payload: ChatRequest) -> Optional[ChatMessage]:
    for message in reversed(payload.messages):
        if message.role.lower().strip() == "user" and message.content.strip():
            return message
    return None


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

    system_prompt = build_system_prompt(transcript)

    api_key = (payload.api_key or settings.openrouter_api_key or "").strip()
    if not api_key:
        return error_response("Missing api_key", status_code=status.HTTP_400_BAD_REQUEST)

    model_name = (payload.model or settings.default_model or "openrouter/auto").strip()

    # Experimental: Use single user message since conversation history is in system prompt
    # openrouter_messages = prepare_openrouter_messages(payload.messages, user_content)
    openrouter_messages = prepare_openrouter_messages_experimental(user_content)

    logger.info(
        "chat request",
        extra={
            "model": model_name,
            "message_length": len(user_content),
            "openrouter_messages": len(openrouter_messages),
        },
    )

    try:
        completion = request_chat_completion(
            model=model_name,
            messages=openrouter_messages,
            system=system_prompt,
            api_key=api_key,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            tools=get_tool_schemas(),
        )
    except OpenRouterError as exc:
        logger.warning("openrouter error", extra={"error": str(exc)})
        return error_response(str(exc), status_code=status.HTTP_502_BAD_GATEWAY)

    assistant_chunks: list[str] = []
    tool_responses: list[str] = []

    choice = (completion.get("choices") or [{}])[0]
    message = choice.get("message") or {}

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        assistant_chunks.append(content)

    tool_calls = message.get("tool_calls") or []
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            name = str(tool_call.get("function", {}).get("name") or "").strip()
            arguments = tool_call.get("function", {}).get("arguments")
            acknowledgement = handle_tool_call(name, arguments)
            if acknowledgement:
                tool_responses.append(acknowledgement)

    if tool_responses:
        assistant_chunks.append("\n".join(tool_responses))

    assistant_text = "".join(assistant_chunks).strip()

    if not assistant_text:
        return error_response("Assistant returned empty response", status_code=status.HTTP_502_BAD_GATEWAY)

    conversation_log.record_agent_message(assistant_text)
    conversation_log.record_reply(assistant_text)

    return PlainTextResponse(assistant_text)
