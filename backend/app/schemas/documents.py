"""
File: backend/app/schemas/documents.py
Purpose: Defines document listing, chunk listing, and deletion API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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


class DocumentChunkSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    child_chunk_id: str
    parent_chunk_id: str
    child_index: int
    parent_index: int
    child_text: str
    parent_text: str
    child_token_count: int
    parent_token_count: int
    source_refs: list[str] = Field(default_factory=list)
    parent_path: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class DocumentChunkListResponse(BaseModel):
    document: DocumentSummary
    total: int
    limit: int
    offset: int
    chunks: list[DocumentChunkSummary] = Field(default_factory=list)


class DocumentDeleteResponse(BaseModel):
    status: Literal["deleted"]
    document_id: str
