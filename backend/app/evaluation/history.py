"""
File: backend/app/evaluation/history.py
Purpose: Persists evaluation run history for trend inspection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
import os
from typing import Any
from uuid import uuid4

from app.core.env import load_environment
from app.core.exceptions import RetrievalError
from app.db.connection import connect_postgres
from app.evaluation.schema import EvaluationRunRequest, EvaluationRunResponse


@dataclass(frozen=True)
class EvaluationRunRecord:
    id: str
    top_k: int
    include_answers: bool
    total_cases: int
    passed_cases: int
    failed_cases: int
    source_hit_rate: float
    answer_term_pass_rate: float | None
    mean_total_ms: float
    response: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class EvaluationRunRecordList:
    total: int
    limit: int
    offset: int
    runs: list[EvaluationRunRecord]


class EvaluationHistoryStore:
    """
    PostgreSQL-backed store for evaluation run history.
    """

    def __init__(self, *, database_url: str | None = None) -> None:
        load_environment()
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for evaluation history",
                code="DATABASE_URL_MISSING",
            )

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id TEXT PRIMARY KEY,
                    top_k INTEGER NOT NULL,
                    include_answers BOOLEAN NOT NULL,
                    total_cases INTEGER NOT NULL,
                    passed_cases INTEGER NOT NULL,
                    failed_cases INTEGER NOT NULL,
                    source_hit_rate DOUBLE PRECISION NOT NULL,
                    answer_term_pass_rate DOUBLE PRECISION,
                    mean_total_ms DOUBLE PRECISION NOT NULL,
                    response_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_evaluation_runs_created
                    ON evaluation_runs(created_at DESC)
                """
            )

    def record_run(
        self,
        *,
        request: EvaluationRunRequest,
        response: EvaluationRunResponse,
    ) -> EvaluationRunRecord:
        self.initialize()
        run_id = str(uuid4())
        payload = response.model_dump(mode="json")
        summary = response.summary
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO evaluation_runs(
                    id,
                    top_k,
                    include_answers,
                    total_cases,
                    passed_cases,
                    failed_cases,
                    source_hit_rate,
                    answer_term_pass_rate,
                    mean_total_ms,
                    response_json
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING *
                """,
                (
                    run_id,
                    request.top_k,
                    request.include_answers,
                    summary.total_cases,
                    summary.passed_cases,
                    summary.failed_cases,
                    summary.source_hit_rate,
                    summary.answer_term_pass_rate,
                    summary.mean_total_ms,
                    self._dumps(payload),
                ),
            ).fetchone()

        return self._record_from_row(row)

    def list_runs(self, *, limit: int = 20, offset: int = 0) -> EvaluationRunRecordList:
        self.initialize()
        with self._connect() as connection:
            total_row = connection.execute(
                "SELECT COUNT(*) AS count FROM evaluation_runs"
            ).fetchone()
            rows = connection.execute(
                """
                SELECT *
                FROM evaluation_runs
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()

        return EvaluationRunRecordList(
            total=int(total_row["count"]),
            limit=limit,
            offset=offset,
            runs=[self._record_from_row(row) for row in rows],
        )

    def get_run(self, run_id: str) -> EvaluationRunRecord | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM evaluation_runs WHERE id = %s",
                (run_id,),
            ).fetchone()
        return self._record_from_row(row) if row else None

    def _connect(self) -> Any:
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for evaluation history"
            ),
        )

    def _record_from_row(self, row: dict[str, Any]) -> EvaluationRunRecord:
        return EvaluationRunRecord(
            id=row["id"],
            top_k=int(row["top_k"]),
            include_answers=bool(row["include_answers"]),
            total_cases=int(row["total_cases"]),
            passed_cases=int(row["passed_cases"]),
            failed_cases=int(row["failed_cases"]),
            source_hit_rate=self._float(row["source_hit_rate"]),
            answer_term_pass_rate=(
                self._float(row["answer_term_pass_rate"])
                if row["answer_term_pass_rate"] is not None
                else None
            ),
            mean_total_ms=self._float(row["mean_total_ms"]),
            response=self._loads(row["response_json"]),
            created_at=row["created_at"],
        )

    def _dumps(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    def _loads(self, value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value

    def _float(self, value: Any) -> float:
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
