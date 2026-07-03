"""
File: backend/app/schemas/admin.py
Purpose: Defines admin dashboard and index-management API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class AdminOverviewHealth(BaseModel):
    status: Literal["ok", "degraded"]
    database_status: Literal["ok", "degraded"]
    embedding_model: str
    llm_model: str
    llm_host: str


class AdminOverviewIndexStats(BaseModel):
    document_count: int
    parent_chunk_count: int
    child_chunk_count: int
    vector_count: int
    readiness_percent: float = Field(ge=0, le=100)


class AdminOverviewQueryCounts(BaseModel):
    total: int
    today: int
    month: int
    year: int
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None


class AdminOverviewIngestionJobs(BaseModel):
    total: int
    queued: int
    running: int
    completed: int
    failed: int
    last_completed_at: datetime | None = None


class AdminOverviewRisk(BaseModel):
    status: Literal["ok", "attention"]
    warning_count: int
    reasons: list[str] = Field(default_factory=list)


class AdminOverviewQuality(BaseModel):
    status: Literal["not_measured"] = "not_measured"
    score_percent: float | None = None


class AdminOverviewRecentTrace(BaseModel):
    id: str
    query: str
    status: Literal["success"]
    result_count: int
    retrieval_ms: float
    answer_ms: float
    total_ms: float
    llm_model: str
    created_at: datetime


class AdminOverviewRecentJob(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    source_kind: str
    file_count: int
    parsed_document_count: int
    indexed_child_count: int
    failure_count: int
    duration_ms: float | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class AdminOverviewResponse(BaseModel):
    health: AdminOverviewHealth
    index: AdminOverviewIndexStats
    queries: AdminOverviewQueryCounts
    ingestion_jobs: AdminOverviewIngestionJobs
    risk: AdminOverviewRisk
    quality: AdminOverviewQuality
    recent_traces: list[AdminOverviewRecentTrace] = Field(default_factory=list)
    recent_jobs: list[AdminOverviewRecentJob] = Field(default_factory=list)
