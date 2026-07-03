"""
File: backend/app/schemas/ingestion.py
Purpose: Defines ingestion job API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IngestionJobEventResponse(BaseModel):
    stage: str
    status: str
    message: str
    path: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: Literal["queued", "running", "completed", "failed"]
    source_kind: str
    source_paths: list[str] = Field(default_factory=list)
    file_count: int
    discovered_input_files: int
    parsed_document_count: int
    chunked_document_count: int
    parent_chunk_count: int
    child_chunk_count: int
    indexed_child_count: int
    failure_count: int
    timings_ms: dict[str, float] = Field(default_factory=dict)
    events: list[IngestionJobEventResponse] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class IngestionJobListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    jobs: list[IngestionJobResponse] = Field(default_factory=list)


class IngestionJobCreateResponse(BaseModel):
    job: IngestionJobResponse
