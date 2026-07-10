from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.constants import SupportedFileType
from app.core.exceptions import RetrievalError
from app.repositories import IndexedDocumentSummary, PgVectorIndexStats
from app.ingestion.jobs import IngestionJobRecord
from app.services import AdminService, DocumentService


def test_document_service_returns_source_file(tmp_path):
    source_path = tmp_path / "policy.md"
    source_path.write_text("# Policy", encoding="utf-8")
    service = DocumentService(
        repository=_FakeDocumentRepository(
            document=_document(source_path=str(source_path)),
        )
    )

    source_file = service.get_document_source("doc-1")

    assert source_file.path == source_path
    assert source_file.file_name == "policy.md"
    assert source_file.media_type == "text/markdown"


def test_document_service_reindex_job_preserves_existing_options(monkeypatch):
    monkeypatch.setenv("DOCU_SEARCH_SKIP_DOTENV", "1")
    monkeypatch.setenv("INGESTION_RUN_MODE", "worker")
    jobs = _FakeIngestionJobs()
    service = DocumentService(
        repository=_FakeDocumentRepository(
            document=_document(source_path="C:/source/policy.md"),
        )
    )

    plan = service.create_reindex_job("doc-1", ingestion_jobs=jobs)

    assert plan.run_in_background is False
    assert plan.job.id == "job-1"
    assert jobs.source_paths == [Path("C:/source/policy.md")]
    assert jobs.source_kind == "reindex"
    assert jobs.options == {
        "recursive": False,
        "clear_index": False,
        "replace": True,
        "continue_on_error": False,
        "document_id": "doc-1",
    }


def test_admin_service_requires_clear_confirmation():
    service = AdminService(document_repository=_FakeDocumentRepository())

    with pytest.raises(RetrievalError) as error:
        service.clear_index(confirm=False)

    assert error.value.code == "INDEX_CLEAR_NOT_CONFIRMED"


class _FakeDocumentRepository:
    def __init__(self, *, document: IndexedDocumentSummary | None = None) -> None:
        self.document = document

    def stats(self):
        return PgVectorIndexStats(
            document_count=1 if self.document else 0,
            parent_chunk_count=0,
            child_chunk_count=0,
            embedding_model="fake",
            embedding_dimensions=3,
        )

    def clear_index(self):
        return self.stats()

    def get_document(self, document_id: str):
        return self.document if document_id == "doc-1" else None


class _FakeIngestionJobs:
    def __init__(self) -> None:
        self.source_paths: list[Path] = []
        self.source_kind: str | None = None
        self.options: dict | None = None

    def create_job(self, *, source_paths, source_kind, options):
        self.source_paths = source_paths
        self.source_kind = source_kind
        self.options = options
        return _job()


def _document(*, source_path: str | None) -> IndexedDocumentSummary:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return IndexedDocumentSummary(
        id="doc-1",
        title="Policy",
        file_name="policy.md",
        file_type=SupportedFileType.MARKDOWN,
        source_path=source_path,
        parent_chunk_count=1,
        child_chunk_count=1,
        created_at=now,
        updated_at=now,
        metadata={},
    )


def _job() -> IngestionJobRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return IngestionJobRecord(
        id="job-1",
        status="queued",
        source_kind="reindex",
        source_paths=["C:/source/policy.md"],
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
        options={},
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
    )
