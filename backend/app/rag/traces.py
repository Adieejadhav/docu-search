"""
File: backend/app/rag/traces.py
Purpose: Persists RAG answer traces for admin inspection and debugging.
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
from app.schemas import SearchResponse


@dataclass(frozen=True)
class RagTraceRecord:
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
    retrieval: dict[str, Any]
    citations: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True)
class RagTraceList:
    total: int
    limit: int
    offset: int
    traces: list[RagTraceRecord]


class RagTraceStore:
    """
    PostgreSQL-backed store for answer/retrieval traces.
    """

    def __init__(self, *, database_url: str | None = None) -> None:
        load_environment()
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for RAG trace persistence",
                code="DATABASE_URL_MISSING",
            )

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_traces (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    llm_model TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    top_k INTEGER NOT NULL,
                    result_count INTEGER NOT NULL,
                    retrieval_ms DOUBLE PRECISION NOT NULL,
                    answer_ms DOUBLE PRECISION NOT NULL,
                    total_ms DOUBLE PRECISION NOT NULL,
                    retrieval_json JSONB NOT NULL,
                    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_traces_created
                    ON rag_traces(created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_rag_traces_query_fts
                    ON rag_traces
                    USING gin (to_tsvector('english', query || ' ' || answer))
                """
            )

    def record_trace(
        self,
        *,
        query: str,
        answer: str,
        llm_model: str,
        retrieval: SearchResponse,
        citations: list[dict[str, Any]],
        retrieval_ms: float,
        answer_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> RagTraceRecord:
        self.initialize()
        trace_id = str(uuid4())
        retrieval_payload = retrieval.model_dump(mode="json")
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO rag_traces(
                    id,
                    query,
                    answer,
                    llm_model,
                    embedding_model,
                    top_k,
                    result_count,
                    retrieval_ms,
                    answer_ms,
                    total_ms,
                    retrieval_json,
                    citations,
                    metadata
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                       %s::jsonb, %s::jsonb, %s::jsonb)
                RETURNING *
                """,
                (
                    trace_id,
                    query,
                    answer,
                    llm_model,
                    retrieval.embedding_model,
                    retrieval.top_k,
                    len(retrieval.results),
                    retrieval_ms,
                    answer_ms,
                    round(retrieval_ms + answer_ms, 3),
                    self._dumps(retrieval_payload),
                    self._dumps(citations),
                    self._dumps(metadata or {}),
                ),
            ).fetchone()

        return self._record_from_row(row)

    def list_traces(
        self,
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> RagTraceList:
        self.initialize()
        with self._connect() as connection:
            total_row = connection.execute(
                "SELECT COUNT(*) AS count FROM rag_traces"
            ).fetchone()
            rows = connection.execute(
                """
                SELECT *
                FROM rag_traces
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()

        return RagTraceList(
            total=int(total_row["count"]),
            limit=limit,
            offset=offset,
            traces=[self._record_from_row(row) for row in rows],
        )

    def get_trace(self, trace_id: str) -> RagTraceRecord | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rag_traces WHERE id = %s",
                (trace_id,),
            ).fetchone()
        return self._record_from_row(row) if row else None

    def delete_traces(self) -> int:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "DELETE FROM rag_traces RETURNING id",
            ).fetchall()
        return len(row)

    def _connect(self) -> Any:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RetrievalError(
                "The psycopg[binary] package is required for RAG trace persistence",
                code="PSYCOPG_PACKAGE_MISSING",
            ) from exc

        return psycopg.connect(self.database_url, row_factory=dict_row)

    def _record_from_row(self, row: dict[str, Any]) -> RagTraceRecord:
        return RagTraceRecord(
            id=row["id"],
            query=row["query"],
            answer=row["answer"],
            llm_model=row["llm_model"],
            embedding_model=row["embedding_model"],
            top_k=int(row["top_k"]),
            result_count=int(row["result_count"]),
            retrieval_ms=self._float(row["retrieval_ms"]),
            answer_ms=self._float(row["answer_ms"]),
            total_ms=self._float(row["total_ms"]),
            retrieval=self._loads(row["retrieval_json"]),
            citations=self._loads(row["citations"]),
            metadata=self._loads(row["metadata"]),
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
