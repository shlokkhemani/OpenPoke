from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..models import GmailConnectPayload, GmailStatusPayload
from ..services import fetch_status, initiate_connect

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.post("/connect")
async def gmail_connect(payload: GmailConnectPayload, settings: Settings = Depends(get_settings)) -> JSONResponse:
    return initiate_connect(payload, settings)


@router.post("/status")
async def gmail_status(payload: GmailStatusPayload) -> JSONResponse:
    return fetch_status(payload)
