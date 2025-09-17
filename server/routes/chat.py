from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..models import ChatHistoryClearResponse, ChatHistoryResponse, ChatRequest
from ..services import get_conversation_log, handle_chat_request

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream", response_class=JSONResponse, summary="Submit a chat message and receive a completion")
async def chat_send(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    return handle_chat_request(payload, settings=settings)


@router.get("/history", response_model=ChatHistoryResponse)
def chat_history() -> ChatHistoryResponse:
    log = get_conversation_log()
    return ChatHistoryResponse(messages=log.to_chat_messages())


@router.delete("/history", response_model=ChatHistoryClearResponse)
def clear_history() -> ChatHistoryClearResponse:
    log = get_conversation_log()
    log.clear()
    return ChatHistoryClearResponse()


__all__ = ["router"]
