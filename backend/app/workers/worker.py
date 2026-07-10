from __future__ import annotations

from time import sleep
from typing import Callable

from app.ingestion.jobs import IngestionJobRecord, IngestionJobService


class IngestionWorker:
    """
    Process-local worker for queued ingestion jobs.
    """

    def __init__(self, *, service: IngestionJobService | None = None) -> None:
        self.service = service or IngestionJobService()

    def run_next(self) -> IngestionJobRecord | None:
        return self.service.run_next_queued_job()

    def run(
        self,
        *,
        poll_seconds: float,
        once: bool,
        on_job_completed: Callable[[IngestionJobRecord], None] | None = None,
        on_idle: Callable[[], None] | None = None,
    ) -> None:
        while True:
            job = self.run_next()
            if job is None:
                if on_idle is not None:
                    on_idle()
                if once:
                    return
                sleep(max(poll_seconds, 0.2))
                continue

            if on_job_completed is not None:
                on_job_completed(job)
            if once:
                return
