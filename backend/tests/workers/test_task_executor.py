from __future__ import annotations

from app.workers import LocalTaskExecutor, WorkerTaskExecutor


def test_local_task_executor_uses_background_adder_when_available():
    service = _FakeIngestionService()
    scheduled: list[tuple[object, str]] = []
    executor = LocalTaskExecutor(ingestion_service=service)

    result = executor.submit_ingestion_job(
        "job-1",
        add_background_task=lambda func, job_id: scheduled.append((func, job_id)),
    )

    assert result.job_id == "job-1"
    assert result.mode == "background"
    assert result.submitted is True
    assert scheduled == [(service.run_job, "job-1")]
    assert service.run_job_ids == []


def test_local_task_executor_runs_inline_without_background_adder():
    service = _FakeIngestionService()
    executor = LocalTaskExecutor(ingestion_service=service)

    result = executor.submit_ingestion_job("job-1")

    assert result.submitted is True
    assert service.run_job_ids == ["job-1"]


def test_worker_task_executor_leaves_job_queued_for_worker():
    executor = WorkerTaskExecutor()

    result = executor.submit_ingestion_job("job-1")

    assert result.job_id == "job-1"
    assert result.mode == "worker"
    assert result.submitted is False


class _FakeIngestionService:
    def __init__(self) -> None:
        self.run_job_ids: list[str] = []

    def run_job(self, job_id: str) -> None:
        self.run_job_ids.append(job_id)
