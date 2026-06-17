"""
File: backend/app/schemas/api.py
Purpose: Defines stable HTTP request/response schemas for the backend API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ingestion.validators.block_validator import clean_required_text


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class HealthServiceStatus(BaseModel):
    status: Literal["ok", "degraded"]
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    database: HealthServiceStatus
    embedding: HealthServiceStatus
    llm: HealthServiceStatus


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    file_name: str | None = None
    file_type: str | None = None
    document_id: str | None = None

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        return clean_required_text(value)


class RetrievedChunkResponse(BaseModel):
    rank: int = Field(ge=1)
    score: float
    file_name: str | None = None
    file_type: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    parent_path: list[str] = Field(default_factory=list)
    child_chunk_id: str
    parent_chunk_id: str
    child_text: str
    parent_text: str


class SearchResponse(BaseModel):
    query: str
    embedding_model: str
    top_k: int
    results: list[RetrievedChunkResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskRequest(SearchRequest):
    pass


class AskResponse(BaseModel):
    query: str
    answer: str
    llm_model: str
    retrieval: SearchResponse
    citations: list[dict[str, Any]] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    file_name: str
    file_type: str
    source_path: str | None = None
    parent_chunk_count: int
    child_chunk_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    documents: list[DocumentSummary] = Field(default_factory=list)


class AdminClearIndexRequest(BaseModel):
    confirm: bool = Field(
        default=False,
        description="Must be true to clear indexed documents, chunks, and embeddings.",
    )


class AdminClearIndexResponse(BaseModel):
    status: Literal["cleared"]
    document_count: int
    parent_chunk_count: int
    child_chunk_count: int
