"""
File: backend/app/schemas/chat.py
Purpose: Defines chat session and chat answer API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.search import AskResponse, RetrievedChunkResponse, SearchRequest


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    trace_id: str | None = None
    llm_model: str | None = None
    latency_ms: float | None = None
    sources: list[RetrievedChunkResponse] = Field(default_factory=list)
    created_at: datetime


class ChatSessionDetail(ChatSessionSummary):
    messages: list[ChatMessageResponse] = Field(default_factory=list)


class ChatSessionListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    sessions: list[ChatSessionSummary] = Field(default_factory=list)


class ChatAskRequest(SearchRequest):
    session_id: str | None = None


class ChatAskResponse(BaseModel):
    session: ChatSessionSummary
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    answer: AskResponse


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=160)


class ChatSessionDeleteResponse(BaseModel):
    status: Literal["deleted"]
    session_id: str
