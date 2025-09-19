from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str = Field(..., min_length=1)
    content: str = Field(...)
    timestamp: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _coerce_content(cls, data: Any) -> Any:
        if isinstance(data, dict) and "content" in data:
            data["content"] = "" if data["content"] is None else str(data["content"])
        return data

    def as_openrouter(self) -> Dict[str, str]:
        return {"role": self.role.strip(), "content": self.content}


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    messages: List[ChatMessage] = Field(default_factory=list)
    api_key: Optional[str] = Field(default=None, alias="api_key")
    model: Optional[str] = None
    system: Optional[str] = None
    stream: bool = True

    @model_validator(mode="before")
    @classmethod
    def _alias_support(cls, data: Any) -> Any:
        if isinstance(data, dict) and "apiKey" in data and "api_key" not in data:
            data["api_key"] = data["apiKey"]
        return data

    def openrouter_messages(self) -> List[Dict[str, str]]:
        return [msg.as_openrouter() for msg in self.messages if msg.content.strip()]


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)


class ChatHistoryClearResponse(BaseModel):
    ok: bool = True
