from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..models import GmailFetchPayload
from ..services import fetch_emails

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/gmail/fetch")
async def gmail_fetch(payload: GmailFetchPayload) -> JSONResponse:
    return fetch_emails(payload)
