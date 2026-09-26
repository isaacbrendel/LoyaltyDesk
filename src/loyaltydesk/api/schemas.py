from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from loyaltydesk.models import AnalystAnswer


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(default="demo", min_length=1, max_length=64)


class ChatResponse(BaseModel):
    answer: AnalystAnswer
    session_id: str
    run_id: str
    blocked: bool = False
    block_reason: list[str] = Field(default_factory=list)
    traces: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    version: str
    warehouse_ready: bool
    llm_provider: str
