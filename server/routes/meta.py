from __future__ import annotations

from fastapi import APIRouter, Depends

from ..config import Settings, get_settings
from ..models import HealthResponse, RootResponse

router = APIRouter(tags=["meta"])

PUBLIC_ENDPOINTS = [
    "/api/v1/chat/send",
    "/api/v1/chat/history",
    "/api/v1/integrations/composio/gmail/connect",
    "/api/v1/integrations/composio/gmail/status",
    "/api/v1/tools/gmail/fetch",
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
