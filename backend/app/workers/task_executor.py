"""
File: backend/app/workers/task_executor.py
Purpose: Defines the boundary for submitting long-running ingestion work.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.services.ingestion_service import IngestionService

BackgroundTaskAdder = Callable[[Callable[[str], None], str], None]


@dataclass(frozen=True)
class TaskSubmission:
    job_id: str
    mode: str
    submitted: bool


class TaskExecutor(Protocol):
    def submit_ingestion_job(
        self,
        job_id: str,
        *,
        add_background_task: BackgroundTaskAdder | None = None,
    ) -> TaskSubmission:
        ...


class LocalTaskExecutor:
    """Submits ingestion work to the current API process."""

    def __init__(self, *, ingestion_service: IngestionService) -> None:
        self.ingestion_service = ingestion_service

    def submit_ingestion_job(
        self,
        job_id: str,
        *,
        add_background_task: BackgroundTaskAdder | None = None,
    ) -> TaskSubmission:
        if add_background_task is not None:
            add_background_task(self.ingestion_service.run_job, job_id)
        else:
            self.ingestion_service.run_job(job_id)
        return TaskSubmission(job_id=job_id, mode="background", submitted=True)


class WorkerTaskExecutor:
    """
    Leaves queued ingestion jobs for the external worker process.

    This is not a durable distributed queue; jobs are durable only because their
    state is stored in PostgreSQL and the worker polls queued records.
    """

    def submit_ingestion_job(
        self,
        job_id: str,
        *,
        add_background_task: BackgroundTaskAdder | None = None,
    ) -> TaskSubmission:
        return TaskSubmission(job_id=job_id, mode="worker", submitted=False)
