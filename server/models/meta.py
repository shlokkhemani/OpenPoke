from __future__ import annotations

from typing import List

from pydantic import BaseModel


class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str


class RootResponse(BaseModel):
    status: str
    service: str
    version: str
    endpoints: List[str]
