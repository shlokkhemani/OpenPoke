from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GmailConnectPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, alias="user_id")
    auth_config_id: Optional[str] = Field(default=None, alias="auth_config_id")


class GmailStatusPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, alias="user_id")
    connection_request_id: Optional[str] = Field(default=None, alias="connection_request_id")


class GmailDisconnectPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[str] = Field(default=None, alias="user_id")
    connection_id: Optional[str] = Field(default=None, alias="connection_id")
    connection_request_id: Optional[str] = Field(default=None, alias="connection_request_id")
