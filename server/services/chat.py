import asyncio
from typing import Optional, Union

from fastapi import status
from fastapi.responses import JSONResponse, PlainTextResponse

from ..agents.interaction_agent.runtime import InteractionAgentRuntime
from ..logging_config import logger
from ..models import ChatMessage, ChatRequest
from ..utils import error_response


def _extract_latest_user_message(payload: ChatRequest) -> Optional[ChatMessage]:
    for message in reversed(payload.messages):
        if message.role.lower().strip() == "user" and message.content.strip():
            return message
    return None


async def handle_chat_request(payload: ChatRequest) -> Union[PlainTextResponse, JSONResponse]:
    """Handle a chat request using the InteractionAgentRuntime."""

    # Extract user message
    user_message = _extract_latest_user_message(payload)
    if user_message is None:
        return error_response("Missing user message", status_code=status.HTTP_400_BAD_REQUEST)

    user_content = user_message.content.strip()  # Already checked in _extract_latest_user_message

    logger.info("chat request", extra={"message_length": len(user_content)})

    try:
        runtime = InteractionAgentRuntime()
    except ValueError as ve:
        # Missing API key error
        logger.error("configuration error", extra={"error": str(ve)})
        return error_response(str(ve), status_code=status.HTTP_400_BAD_REQUEST)

    async def _run_interaction() -> None:
        try:
            await runtime.execute(user_message=user_content)
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("chat task failed", extra={"error": str(exc)})

    asyncio.create_task(_run_interaction())

    return PlainTextResponse("", status_code=status.HTTP_202_ACCEPTED)
