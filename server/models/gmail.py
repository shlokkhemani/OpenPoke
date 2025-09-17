from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class GmailConnectPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, alias="user_id")
    auth_config_id: Optional[str] = Field(default=None, alias="auth_config_id")


class GmailStatusPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, alias="user_id")
    connection_request_id: Optional[str] = Field(default=None, alias="connection_request_id")


class GmailFetchPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user_id: str = Field(..., alias="user_id")
    arguments: Optional[Dict[str, Any]] = None
    max_results: Optional[int] = Field(default=None, alias="max_results")
    include_payload: Optional[bool] = Field(default=None, alias="include_payload")
    verbose: Optional[bool] = Field(default=None)
