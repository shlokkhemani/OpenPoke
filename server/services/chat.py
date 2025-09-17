from __future__ import annotations

import secrets
from typing import List, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from ..config import Settings
from ..logging_config import logger
from ..models import ChatRequest
from ..openrouter_client import OpenRouterError, stream_chat_completion
from ..prompts import get_interaction_system_prompt
from ..utils import error_response, sse_iter
from .history import chat_history_store


def build_chat_stream_response(
    payload: ChatRequest,
    *,
    request: Optional[Request],
    settings: Settings,
    request_id: Optional[str] = None,
) -> StreamingResponse | JSONResponse:
    messages = payload.openrouter_messages()
    if not messages:
        return error_response("Missing messages or prompt", status_code=status.HTTP_400_BAD_REQUEST)

    api_key = (payload.api_key or settings.openrouter_api_key or "").strip()
    if not api_key:
        return error_response("Missing api_key", status_code=status.HTTP_400_BAD_REQUEST)

    model_name = (payload.model or settings.default_model or "openrouter/auto").strip()
    system_prompt = (payload.system or "").strip() or get_interaction_system_prompt()

    chat_history_store.replace(messages)

    if not request_id:
        request_id = secrets.token_hex(8)

    logger.info(
        "chat request",
        extra={
            "model": model_name,
            "messages": len(messages),
            "has_system": bool(system_prompt),
            "request_id": request_id,
        },
    )

    try:
        deltas = stream_chat_completion(
            model=model_name,
            messages=messages,
            system=system_prompt,
            api_key=api_key,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
    except OpenRouterError as exc:
        logger.warning("openrouter error", extra={"error": str(exc), "request_id": request_id})
        return error_response(str(exc), status_code=status.HTTP_502_BAD_GATEWAY)

    assistant_chunks: List[str] = []
    stream_completed = False

    def history_tracked_deltas():
        nonlocal stream_completed
        try:
            for delta in deltas:
                if delta.get("type") == "content":
                    text = str(delta.get("text") or "")
                    if text:
                        assistant_chunks.append(text)
                elif delta.get("type") == "event" and delta.get("event") == "done":
                    stream_completed = True
                yield delta
        finally:
            if stream_completed and assistant_chunks:
                chat_history_store.append({"role": "assistant", "content": "".join(assistant_chunks)})

    tracked_deltas = history_tracked_deltas()

    async def event_source():
        async for chunk in iterate_in_threadpool(sse_iter(tracked_deltas)):
            yield chunk

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-OpenPoke-Model": model_name,
        "X-Request-ID": request_id,
    }
    if request and request.client:
        headers["X-Client-Host"] = request.client.host

    return StreamingResponse(event_source(), media_type="text/event-stream; charset=utf-8", headers=headers)
