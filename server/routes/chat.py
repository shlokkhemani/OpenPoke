from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..models import ChatHistoryClearResponse, ChatHistoryResponse, ChatRequest
from ..services import get_conversation_log, handle_chat_request

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/send", response_class=JSONResponse, summary="Submit a chat message and receive a completion")
async def chat_send(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    return await handle_chat_request(payload, settings=settings)


@router.get("/history", response_model=ChatHistoryResponse)
def chat_history() -> ChatHistoryResponse:
    log = get_conversation_log()
    return ChatHistoryResponse(messages=log.to_chat_messages())


@router.delete("/history", response_model=ChatHistoryClearResponse)
def clear_history() -> ChatHistoryClearResponse:
    from ..services import get_execution_agent_logs, get_agent_roster

    # Clear conversation log
    log = get_conversation_log()
    log.clear()

    # Clear execution agent logs
    execution_logs = get_execution_agent_logs()
    execution_logs.clear_all()

    # Clear agent roster
    roster = get_agent_roster()
    roster.clear()

    return ChatHistoryClearResponse()


__all__ = ["router"]
