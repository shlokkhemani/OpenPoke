from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse


def error_response(message: str, *, status_code: int, detail: Optional[str] = None) -> JSONResponse:
    payload: Dict[str, Any] = {"ok": False, "error": message}
    if detail is not None:
        payload["detail"] = detail
    return JSONResponse(payload, status_code=status_code)
