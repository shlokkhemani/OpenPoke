"""Response utilities."""

from typing import Optional

from fastapi.responses import JSONResponse


def error_response(message: str, *, status_code: int, detail: Optional[str] = None) -> JSONResponse:
    """Create a standardized error response."""
    payload = {"ok": False, "error": message}
    if detail:
        payload["detail"] = detail
    return JSONResponse(payload, status_code=status_code)