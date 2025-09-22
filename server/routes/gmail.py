from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..models import GmailConnectPayload, GmailDisconnectPayload, GmailStatusPayload
from ..services import disconnect_account, fetch_status, initiate_connect

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.post("/connect")
# Initiate Gmail OAuth connection flow through Composio
async def gmail_connect(payload: GmailConnectPayload, settings: Settings = Depends(get_settings)) -> JSONResponse:
    return initiate_connect(payload, settings)


@router.post("/status")
# Check the current Gmail connection status and user information
async def gmail_status(payload: GmailStatusPayload) -> JSONResponse:
    return fetch_status(payload)


@router.post("/disconnect")
# Disconnect Gmail account and clear cached profile data
async def gmail_disconnect(payload: GmailDisconnectPayload) -> JSONResponse:
    return disconnect_account(payload)
