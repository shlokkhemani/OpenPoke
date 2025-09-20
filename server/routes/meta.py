from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..config import Settings, get_settings
from ..models import (
    HealthResponse,
    RootResponse,
    SetTimezoneRequest,
    SetTimezoneResponse,
)
from ..services import get_timezone_store

router = APIRouter(tags=["meta"])

@router.get("/health", response_model=HealthResponse)
# Return service health status for monitoring and load balancers
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(ok=True, service="openpoke", version=settings.app_version)


@router.get("/meta", response_model=RootResponse)
# Return service metadata including available API endpoints
def meta(request: Request, settings: Settings = Depends(get_settings)) -> RootResponse:
    endpoints = sorted(
        {
            route.path
            for route in request.app.routes
            if getattr(route, "include_in_schema", False) and route.path.startswith("/api/")
        }
    )
    return RootResponse(
        status="ok",
        service="openpoke",
        version=settings.app_version,
        endpoints=endpoints,
    )


@router.post("/meta/timezone", response_model=SetTimezoneResponse)
# Set the user's timezone for proper email timestamp formatting
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
