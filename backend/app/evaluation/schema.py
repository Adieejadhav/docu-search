"""
File: backend/app/evaluation/schema.py
Purpose: Defines RAG evaluation suite request, case, and result models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.ingestion.validators.block_validator import clean_required_text


class EvaluationCase(BaseModel):
    id: str
    question: str
    expected_answer_terms: list[str] = Field(default_factory=list)
    expected_context_terms: list[str] = Field(default_factory=list)
    expected_source_files: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("id", "question")
    @classmethod
    def clean_required_fields(cls, value: str) -> str:
        return clean_required_text(value)


class EvaluationRunRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    include_answers: bool = True
    case_ids: list[str] | None = None


class EvaluationContext(BaseModel):
    rank: int
    score: float
    file_name: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    parent_path: list[str] = Field(default_factory=list)
    text_excerpt: str


class EvaluationCaseResult(BaseModel):
    case_id: str
    question: str
    status: Literal["passed", "failed"]
    retrieval_passed: bool
    answer_passed: bool | None = None
    source_rank: int | None = None
    missing_context_terms: list[str] = Field(default_factory=list)
    missing_answer_terms: list[str] = Field(default_factory=list)
    answer: str | None = None
    llm_model: str | None = None
    retrieval_ms: float
    answer_ms: float | None = None
    total_ms: float
    contexts: list[EvaluationContext] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)


class EvaluationRunSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    retrieval_passed_cases: int
    answer_passed_cases: int | None = None
    source_hit_rate: float
    answer_term_pass_rate: float | None = None
    mean_retrieval_ms: float
    mean_answer_ms: float | None = None
    mean_total_ms: float


class EvaluationRunResponse(BaseModel):
    top_k: int
    include_answers: bool
    summary: EvaluationRunSummary
    cases: list[EvaluationCase]
    results: list[EvaluationCaseResult]
