"""
File: backend/app/repositories/job_repository.py
Purpose: Owns ingestion job persistence and state transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from typing import Any, Literal
from uuid import uuid4

from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.integrations.database import DatabasePool, connect_postgres

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True)
class IngestionJobRecord:
    id: str
    status: JobStatus
    source_kind: str
    source_paths: list[str]
    file_count: int
    discovered_input_files: int
    parsed_document_count: int
    chunked_document_count: int
    parent_chunk_count: int
    child_chunk_count: int
    indexed_child_count: int
    failure_count: int
    timings_ms: dict[str, float]
    events: list[dict[str, Any]]
    error_code: str | None
    error_message: str | None
    error_details: dict[str, Any]
    options: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass(frozen=True)
class IngestionJobList:
    total: int
    limit: int
    offset: int
    jobs: list[IngestionJobRecord] = field(default_factory=list)


class JobRepository:
    """PostgreSQL-backed repository for API ingestion job state."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        database_pool: DatabasePool | None = None,
    ) -> None:
        self.database_pool = database_pool
        self.database_url = database_url or getattr(database_pool, "database_url", None)
        self.database_url = self.database_url or get_settings().database.url
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for ingestion jobs",
                code="DATABASE_URL_MISSING",
            )

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    source_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    discovered_input_files INTEGER NOT NULL DEFAULT 0,
                    parsed_document_count INTEGER NOT NULL DEFAULT 0,
                    chunked_document_count INTEGER NOT NULL DEFAULT 0,
                    parent_chunk_count INTEGER NOT NULL DEFAULT 0,
                    child_chunk_count INTEGER NOT NULL DEFAULT 0,
                    indexed_child_count INTEGER NOT NULL DEFAULT 0,
                    failure_count INTEGER NOT NULL DEFAULT 0,
                    timings_ms JSONB NOT NULL DEFAULT '{}'::jsonb,
                    events JSONB NOT NULL DEFAULT '[]'::jsonb,
                    error_code TEXT,
                    error_message TEXT,
                    error_details JSONB NOT NULL DEFAULT '{}'::jsonb,
                    options JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status_created
                    ON ingestion_jobs(status, created_at DESC)
                """
            )

    def create_job(
        self,
        *,
        source_kind: str,
        source_paths: list[str],
        options: dict[str, Any],
    ) -> IngestionJobRecord:
        self.initialize()
        job_id = str(uuid4())
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO ingestion_jobs(
                    id,
                    status,
                    source_kind,
                    source_paths,
                    file_count,
                    options
                )
                VALUES(%s, 'queued', %s, %s::jsonb, %s, %s::jsonb)
                RETURNING *
                """,
                (
                    job_id,
                    source_kind,
                    self._dumps(source_paths),
                    len(source_paths),
                    self._dumps(options),
                ),
            ).fetchone()
        return self._job_from_row(row)

    def mark_running(self, job_id: str) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (job_id,),
            )

    def append_event(self, job_id: str, event: Any) -> None:
        event_payload = {
            "stage": event.stage,
            "status": event.status,
            "message": event.message,
            "path": event.path,
            "duration_ms": event.duration_ms,
            "metadata": event.metadata,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_jobs
                SET events = events || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (self._dumps([event_payload]), job_id),
            )

    def complete_job(self, job_id: str, result: Any) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'completed',
                    discovered_input_files = %s,
                    parsed_document_count = %s,
                    chunked_document_count = %s,
                    parent_chunk_count = %s,
                    child_chunk_count = %s,
                    indexed_child_count = %s,
                    failure_count = %s,
                    timings_ms = %s::jsonb,
                    error_code = NULL,
                    error_message = NULL,
                    error_details = '{}'::jsonb,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    result.input_count,
                    result.parsed_document_count,
                    result.chunked_document_count,
                    result.parent_chunk_count,
                    result.child_chunk_count,
                    result.indexed_child_count,
                    result.failure_count,
                    self._dumps(result.timings_ms),
                    job_id,
                ),
            )

    def fail_job(
        self,
        job_id: str,
        *,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'failed',
                    error_code = %s,
                    error_message = %s,
                    error_details = %s::jsonb,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (code, message, self._dumps(details or {}), job_id),
            )

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE id = %s",
                (job_id,),
            ).fetchone()
        return self._job_from_row(row) if row else None

    def claim_next_queued_job(self) -> IngestionJobRecord | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE ingestion_jobs
                SET status = 'running',
                    started_at = COALESCE(started_at, NOW()),
                    updated_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM ingestion_jobs
                    WHERE status = 'queued'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
                """
            ).fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(self, *, limit: int = 20, offset: int = 0) -> IngestionJobList:
        self.initialize()
        with self._connect() as connection:
            total_row = connection.execute(
                "SELECT COUNT(*) AS count FROM ingestion_jobs"
            ).fetchone()
            rows = connection.execute(
                """
                SELECT *
                FROM ingestion_jobs
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()
        return IngestionJobList(
            total=int(total_row["count"]),
            limit=limit,
            offset=offset,
            jobs=[self._job_from_row(row) for row in rows],
        )

    def _connect(self) -> Any:
        if self.database_pool is not None:
            return self.database_pool.connection()
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for ingestion jobs"
            ),
        )

    def _job_from_row(self, row: dict[str, Any]) -> IngestionJobRecord:
        return IngestionJobRecord(
            id=row["id"],
            status=row["status"],
            source_kind=row["source_kind"],
            source_paths=self._loads(row["source_paths"]),
            file_count=int(row["file_count"]),
            discovered_input_files=int(row["discovered_input_files"]),
            parsed_document_count=int(row["parsed_document_count"]),
            chunked_document_count=int(row["chunked_document_count"]),
            parent_chunk_count=int(row["parent_chunk_count"]),
            child_chunk_count=int(row["child_chunk_count"]),
            indexed_child_count=int(row["indexed_child_count"]),
            failure_count=int(row["failure_count"]),
            timings_ms=self._loads(row["timings_ms"]),
            events=self._loads(row["events"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
            error_details=self._loads(row["error_details"]),
            options=self._loads(row["options"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )

    def _dumps(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    def _loads(self, value: Any) -> Any:
        return json.loads(value) if isinstance(value, str) else value


IngestionJobStore = JobRepository
