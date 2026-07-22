"""
File: backend/app/ingestion/jobs.py
Purpose: Coordinates ingestion job execution for API-driven document indexing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import IngestionError, RetrievalError
from app.ingestion.orchestrator import IngestionOrchestrator
from app.repositories.job_repository import (
    IngestionJobList,
    IngestionJobRecord,
    IngestionJobStore,
    JobRepository,
    JobStatus,
)


class IngestionJobService:
    """
    Creates and executes ingestion jobs using the production orchestrator.
    """

    def __init__(
        self,
        *,
        store: JobRepository | None = None,
        orchestrator: IngestionOrchestrator | None = None,
        upload_root: Path | None = None,
    ) -> None:
        self.store = store or JobRepository()
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
            self._fail_job_from_exception(job_id, exc)

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
            self._fail_job_from_exception(job.id, exc)

        return self.store.get_job(job.id)

    def _fail_job_from_exception(self, job_id: str, exc: Exception) -> None:
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


def default_upload_root() -> Path:
    upload_root = get_settings().ingestion.upload_root
    if upload_root is not None:
        return upload_root

    return Path(__file__).resolve().parents[3] / "storage" / "uploads"


__all__ = [
    "IngestionJobList",
    "IngestionJobRecord",
    "IngestionJobService",
    "IngestionJobStore",
    "JobRepository",
    "JobStatus",
    "default_upload_root",
]
