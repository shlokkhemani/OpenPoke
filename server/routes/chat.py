from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse

from ..config import Settings, get_settings
from ..models import ChatHistoryClearResponse, ChatHistoryResponse, ChatMessage, ChatRequest
from ..services import build_chat_stream_response, chat_history_store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream", response_class=StreamingResponse, summary="Stream chat completions")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    request_id = request.headers.get("x-request-id")
    return build_chat_stream_response(payload, request=request, settings=settings, request_id=request_id)


@router.get("/history", response_model=ChatHistoryResponse)
def get_history() -> ChatHistoryResponse:
    history = [ChatMessage.model_validate(item) for item in chat_history_store.get_history()]
    return ChatHistoryResponse(messages=history)


@router.delete("/history", response_model=ChatHistoryClearResponse)
def clear_history() -> ChatHistoryClearResponse:
    chat_history_store.clear()
    return ChatHistoryClearResponse()
