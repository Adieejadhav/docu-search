from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import IngestionSettings
from app.ingestion.jobs import IngestionJobList, IngestionJobRecord
from app.services.ingestion_service import (
    IngestionService,
    IngestionUploadOptions,
    sanitize_upload_relative_path,
    should_skip_upload_file,
    sanitize_upload_filename,
    unique_destination,
)


def test_create_upload_job_writes_files_and_creates_background_plan(tmp_path):
    job_service = _FakeIngestionJobService(upload_root=tmp_path)
    service = IngestionService(
        job_service=job_service,
        settings=IngestionSettings(
            run_mode="background",
            max_upload_files=2,
            max_upload_file_size_bytes=1024,
        ),
    )
    upload = _FakeUpload(filename="team notes.txt", content=b"hello team")

    plan = asyncio.run(
        service.create_upload_job(
            files=[upload],
            options=IngestionUploadOptions(
                clear_index=True,
                replace=False,
                continue_on_error=False,
            ),
        )
    )

    assert plan.run_in_background is True
    assert plan.job.id == "job-1"
    assert upload.closed is True
    assert len(job_service.source_paths) == 1
    assert job_service.source_paths[0].name == "team_notes.txt"
    assert job_service.source_paths[0].read_bytes() == b"hello team"
    assert job_service.options == {
        "recursive": False,
        "clear_index": True,
        "replace": False,
        "continue_on_error": False,
    }


def test_list_and_get_jobs_delegate_to_job_store(tmp_path):
    job_service = _FakeIngestionJobService(upload_root=tmp_path)
    service = IngestionService(
        job_service=job_service,
        settings=IngestionSettings(run_mode="worker"),
    )

    listed = service.list_jobs(limit=10, offset=0)
    found = service.get_job("job-1")

    assert listed.total == 1
    assert found.id == "job-1"


def test_upload_filename_helpers_match_route_compatibility(tmp_path):
    existing = tmp_path / "report.txt"
    existing.write_text("first", encoding="utf-8")

    assert sanitize_upload_filename("../report final.txt") == "report_final.txt"
    assert sanitize_upload_relative_path("team docs/run book.txt") == Path(
        "team_docs",
        "run_book.txt",
    )
    assert should_skip_upload_file("team docs/~$run book.docx") is True
    assert should_skip_upload_file("team docs/~$_aquila_docx_procedure_fixture.docx") is True
    assert should_skip_upload_file("team docs/__aquila_docx_procedure_fixture.docx") is True
    assert unique_destination(tmp_path, "report.txt") == tmp_path / "report-2.txt"


def test_create_upload_job_preserves_folder_paths_and_skips_temp_files(tmp_path):
    job_service = _FakeIngestionJobService(upload_root=tmp_path)
    service = IngestionService(
        job_service=job_service,
        settings=IngestionSettings(
            run_mode="background",
            max_upload_files=3,
            max_upload_file_size_bytes=1024,
        ),
    )
    upload = _FakeUpload(filename="team docs/run book.txt", content=b"hello team")
    temp_upload = _FakeUpload(
        filename="team docs/~$_aquila_docx_procedure_fixture.docx",
        content=b"lock",
    )

    plan = asyncio.run(
        service.create_upload_job(
            files=[upload, temp_upload],
            options=IngestionUploadOptions(
                clear_index=False,
                replace=True,
                continue_on_error=True,
            ),
        )
    )

    assert plan.job.id == "job-1"
    assert upload.closed is True
    assert temp_upload.closed is True
    assert len(job_service.source_paths) == 1
    relative_parts = job_service.source_paths[0].relative_to(tmp_path).parts
    assert relative_parts[1:] == ("team_docs", "run_book.txt")
    assert job_service.source_paths[0].read_bytes() == b"hello team"


class _FakeUpload:
    def __init__(self, *, filename: str, content: bytes) -> None:
        self.filename = filename
        self._content = content
        self._read = False
        self.closed = False

    async def read(self, _size: int = -1) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._content

    async def close(self) -> None:
        self.closed = True


class _FakeIngestionJobStore:
    def __init__(self, job: IngestionJobRecord) -> None:
        self.job = job

    def list_jobs(self, *, limit: int, offset: int) -> IngestionJobList:
        return IngestionJobList(total=1, limit=limit, offset=offset, jobs=[self.job])

    def get_job(self, job_id: str) -> IngestionJobRecord | None:
        return self.job if job_id == self.job.id else None


class _FakeIngestionJobService:
    def __init__(self, *, upload_root: Path) -> None:
        self.upload_root = upload_root
        self.job = _ingestion_job()
        self.store = _FakeIngestionJobStore(self.job)
        self.source_paths: list[Path] = []
        self.options: dict | None = None

    def create_job(
        self,
        *,
        source_paths: list[Path],
        options: dict,
        source_kind: str = "upload",
    ) -> IngestionJobRecord:
        self.source_paths = source_paths
        self.options = options
        self.job = _ingestion_job(
            source_paths=[str(path) for path in source_paths],
            source_kind=source_kind,
            options=options,
        )
        self.store.job = self.job
        return self.job

    def run_job(self, job_id: str) -> None:
        assert job_id == self.job.id


def _ingestion_job(
    *,
    source_paths: list[str] | None = None,
    source_kind: str = "upload",
    options: dict | None = None,
) -> IngestionJobRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return IngestionJobRecord(
        id="job-1",
        status="queued",
        source_kind=source_kind,
        source_paths=source_paths or ["policy.md"],
        file_count=1,
        discovered_input_files=0,
        parsed_document_count=0,
        chunked_document_count=0,
        parent_chunk_count=0,
        child_chunk_count=0,
        indexed_child_count=0,
        failure_count=0,
        timings_ms={},
        events=[],
        error_code=None,
        error_message=None,
        error_details={},
        options=options or {},
        created_at=now,
        updated_at=now,
    )
