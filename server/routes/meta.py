from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..config import Settings, get_settings
from ..models import (
    HealthResponse,
    RootResponse,
    SetTimezoneRequest,
    SetTimezoneResponse,
)
from ..services import get_timezone_store

router = APIRouter(tags=["meta"])

PUBLIC_ENDPOINTS = [
    "/api/v1/chat/send",
    "/api/v1/chat/history",
    "/api/v1/integrations/composio/gmail/connect",
    "/api/v1/integrations/composio/gmail/status",
    "/api/v1/tools/gmail/fetch",
    "/api/v1/meta/timezone",
]


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(ok=True, service="openpoke", version=settings.app_version)


@router.get("/meta", response_model=RootResponse)
def meta(settings: Settings = Depends(get_settings)) -> RootResponse:
    return RootResponse(
        status="ok",
        service="openpoke",
        version=settings.app_version,
        endpoints=["/api/v1/health", "/api/v1/meta", *PUBLIC_ENDPOINTS],
    )


@router.post("/meta/timezone", response_model=SetTimezoneResponse)
def set_timezone(payload: SetTimezoneRequest) -> SetTimezoneResponse:
    store = get_timezone_store()
    try:
        store.set_timezone(payload.timezone)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return SetTimezoneResponse(timezone=store.get_timezone())


@router.get("/meta/timezone", response_model=SetTimezoneResponse)
def get_timezone() -> SetTimezoneResponse:
    store = get_timezone_store()
    return SetTimezoneResponse(timezone=store.get_timezone())
