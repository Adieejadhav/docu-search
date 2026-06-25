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


class PipelineNodeTestResponse(BaseModel):
    stage: Literal["validate", "parse", "chunk", "embed", "index"]
    status: Literal["completed"]
    duration_ms: float = Field(ge=0)
    summary: dict[str, Any] = Field(default_factory=dict)
    preview: list[dict[str, Any]] = Field(default_factory=list)


class AskRequest(SearchRequest):
    pass


class AskResponse(BaseModel):
    query: str
    answer: str
    llm_model: str
    retrieval: SearchResponse
    citations: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None


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


class AdminOverviewQueryCounts(BaseModel):
    total: int
    today: int
    month: int
    year: int


class AdminOverviewIngestionJobs(BaseModel):
    total: int
    queued: int
    running: int
    completed: int
    failed: int


class AdminOverviewResponse(BaseModel):
    document_count: int
    parent_chunk_count: int
    child_chunk_count: int
    vector_count: int
    queries: AdminOverviewQueryCounts
    ingestion_jobs: AdminOverviewIngestionJobs


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


class EvaluationRunRecordSummary(BaseModel):
    id: str
    top_k: int
    include_answers: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    source_hit_rate: float
    answer_term_pass_rate: float | None = None
    mean_total_ms: float
    created_at: datetime


class EvaluationRunRecordDetail(EvaluationRunRecordSummary):
    response: dict[str, Any]


class EvaluationRunHistoryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    runs: list[EvaluationRunRecordSummary] = Field(default_factory=list)
