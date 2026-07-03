"""
File: backend/app/schemas/traces.py
Purpose: Defines RAG trace API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.search import SearchResponse


class RagTraceSummary(BaseModel):
    id: str
    query: str
    answer: str
    llm_model: str
    embedding_model: str
    top_k: int
    result_count: int
    retrieval_ms: float
    answer_ms: float
    total_ms: float
    created_at: datetime


class RagTraceDetail(RagTraceSummary):
    retrieval: SearchResponse
    citations: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RagTraceListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    traces: list[RagTraceSummary] = Field(default_factory=list)


class RagTraceDeleteResponse(BaseModel):
    status: Literal["deleted"]
    deleted_count: int
