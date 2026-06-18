"""
File: backend/app/ingestion/jobs.py
Purpose: Persists and runs ingestion jobs for API-driven document indexing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.core.env import load_environment
from app.core.exceptions import IngestionError, RetrievalError
from app.ingestion.orchestrator import (
    IngestionOrchestrator,
    IngestionPipelineResult,
    IngestionProgressEvent,
)

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


class IngestionJobStore:
    """
    PostgreSQL-backed store for API ingestion job state.
    """

    def __init__(self, *, database_url: str | None = None) -> None:
        load_environment()
        self.database_url = database_url or os.getenv("DATABASE_URL")
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

    def append_event(self, job_id: str, event: IngestionProgressEvent) -> None:
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

    def complete_job(self, job_id: str, result: IngestionPipelineResult) -> None:
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
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RetrievalError(
                "The psycopg[binary] package is required for ingestion jobs",
                code="PSYCOPG_PACKAGE_MISSING",
            ) from exc

        return psycopg.connect(self.database_url, row_factory=dict_row)

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


class IngestionJobService:
    """
    Creates and executes ingestion jobs using the production orchestrator.
    """

    def __init__(
        self,
        *,
        store: IngestionJobStore | None = None,
        orchestrator: IngestionOrchestrator | None = None,
        upload_root: Path | None = None,
    ) -> None:
        self.store = store or IngestionJobStore()
        self.orchestrator = orchestrator or IngestionOrchestrator()
        self.upload_root = upload_root or default_upload_root()

    def create_job(
        self,
        *,
        source_paths: list[Path],
        options: dict[str, Any],
        source_kind: str = "upload",
    ) -> IngestionJobRecord:
        if not source_paths:
            raise IngestionError(
                "At least one source file is required",
                code="NO_UPLOAD_FILES",
            )
        return self.store.create_job(
            source_kind=source_kind,
            source_paths=[str(path) for path in source_paths],
            options=options,
        )

    def run_job(self, job_id: str) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            raise IngestionError(
                "Ingestion job was not found",
                code="INGESTION_JOB_NOT_FOUND",
                details={"job_id": job_id},
            )

        self.store.mark_running(job_id)
        try:
            result = self.orchestrator.ingest(
                [Path(path) for path in job.source_paths],
                recursive=bool(job.options.get("recursive", False)),
                clear_index=bool(job.options.get("clear_index", False)),
                replace=bool(job.options.get("replace", True)),
                continue_on_error=bool(job.options.get("continue_on_error", True)),
                progress_callback=lambda event: self.store.append_event(job_id, event),
            )
            self.store.complete_job(job_id, result)
        except Exception as exc:
            if isinstance(exc, (IngestionError, RetrievalError)):
                code = exc.code
                message = exc.message
                details = exc.details
            else:
                code = exc.__class__.__name__
                message = str(exc)
                details = {}
            self.store.fail_job(
                job_id,
                code=code,
                message=message,
                details=details,
            )

    def run_next_queued_job(self) -> IngestionJobRecord | None:
        job = self.store.claim_next_queued_job()
        if job is None:
            return None

        try:
            result = self.orchestrator.ingest(
                [Path(path) for path in job.source_paths],
                recursive=bool(job.options.get("recursive", False)),
                clear_index=bool(job.options.get("clear_index", False)),
                replace=bool(job.options.get("replace", True)),
                continue_on_error=bool(job.options.get("continue_on_error", True)),
                progress_callback=lambda event: self.store.append_event(job.id, event),
            )
            self.store.complete_job(job.id, result)
        except Exception as exc:
            if isinstance(exc, (IngestionError, RetrievalError)):
                code = exc.code
                message = exc.message
                details = exc.details
            else:
                code = exc.__class__.__name__
                message = str(exc)
                details = {}
            self.store.fail_job(
                job.id,
                code=code,
                message=message,
                details=details,
            )

        return self.store.get_job(job.id)


def default_upload_root() -> Path:
    raw_root = os.getenv("DOCU_SEARCH_UPLOAD_ROOT")
    if raw_root:
        return Path(raw_root)

    return Path(__file__).resolve().parents[3] / "storage" / "uploads"
