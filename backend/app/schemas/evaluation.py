"""
File: backend/app/schemas/evaluation.py
Purpose: Defines API schemas for persisted evaluation run history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
