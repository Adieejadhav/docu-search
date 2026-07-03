"""
File: backend/app/schemas/search.py
Purpose: Defines search and RAG answer API schemas.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.ingestion.validators.block_validator import clean_required_text


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
    document_id: str | None = None
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
    trace_id: str | None = None
