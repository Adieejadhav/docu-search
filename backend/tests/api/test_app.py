from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_chunk_index,
    get_database_url,
    get_evaluation_history_store,
    get_ingestion_job_service,
    get_pipeline_node_tester,
    get_rag_trace_store,
    get_rag_answerer,
)
from app.core.constants import SupportedFileType
from app.db import DatabaseHealth
from app.indexing import IndexedDocumentSummary, PgVectorIndexStats
from app.ingestion.chunking import ChildChunk, ParentChunk
from app.ingestion.jobs import IngestionJobList, IngestionJobRecord
from app.ingestion.pipeline_testing import PipelineNodeTestResult
from app.main import create_app
from app.rag import RagAnswer
from app.search.retrieval import RetrievedChunk, RetrievalResult


def test_root_returns_service_status():
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "docu-search-backend"


def test_health_returns_configured_services(monkeypatch):
    from app.api.routes import health

    monkeypatch.setattr(
        health,
        "check_database_health",
        lambda _: DatabaseHealth(
            ok=True,
            details={"pgvector_available": True, "tables": {}},
        ),
    )
    app = create_app()
    app.dependency_overrides[get_database_url] = lambda: "postgresql://example/db"
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"]["status"] == "ok"


def test_search_endpoint_returns_ranked_chunks():
    app = create_app()
    app.dependency_overrides[get_chunk_index] = lambda: _FakeIndex()
    client = TestClient(app)

    response = client.post("/search", json={"query": "satellite exception", "top_k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "satellite exception"
    assert payload["results"][0]["file_name"] == "policy.md"
    assert payload["results"][0]["parent_chunk_id"] == "parent-1"


def test_ask_endpoint_returns_answer_and_retrieval():
    app = create_app()
    app.dependency_overrides[get_chunk_index] = lambda: _FakeIndex()
    app.dependency_overrides[get_rag_answerer] = lambda: _FakeAnswerer()
    app.dependency_overrides[get_rag_trace_store] = lambda: _FakeTraceStore()
    client = TestClient(app)

    response = client.post("/ask", json={"query": "Which policy?", "top_k": 1})

    assert response.status_code == 200
    payload = response.json()
    assert "P-004" in payload["answer"]
    assert payload["retrieval"]["results"][0]["child_chunk_id"] == "child-1"


def test_documents_endpoint_lists_indexed_documents():
    app = create_app()
    app.dependency_overrides[get_chunk_index] = lambda: _FakeIndex()
    client = TestClient(app)

    response = client.get("/documents")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["documents"][0]["file_name"] == "policy.md"


def test_admin_clear_requires_confirmation():
    app = create_app()
    app.dependency_overrides[get_chunk_index] = lambda: _FakeIndex()
    client = TestClient(app)

    response = client.post("/admin/index/clear", json={"confirm": False})

    assert response.status_code == 400
    assert response.json()["code"] == "INDEX_CLEAR_NOT_CONFIRMED"


def test_ingestion_upload_creates_background_job():
    app = create_app()
    fake_service = _FakeIngestionJobService()
    app.dependency_overrides[get_ingestion_job_service] = lambda: fake_service
    client = TestClient(app)

    response = client.post(
        "/admin/ingestion/jobs",
        files={"files": ("policy.md", b"# Policy\n\nP-004 syncs within 14 days.", "text/markdown")},
        data={"replace": "true", "continue_on_error": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["id"] == "job-1"
    assert payload["job"]["status"] == "queued"
    assert fake_service.run_job_ids == ["job-1"]


def test_ingestion_jobs_can_be_listed_and_read():
    app = create_app()
    fake_service = _FakeIngestionJobService()
    app.dependency_overrides[get_ingestion_job_service] = lambda: fake_service
    client = TestClient(app)

    list_response = client.get("/admin/ingestion/jobs")
    get_response = client.get("/admin/ingestion/jobs/job-1")

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert get_response.status_code == 200
    assert get_response.json()["id"] == "job-1"


def test_pipeline_node_can_be_tested_with_uploaded_file():
    app = create_app()
    fake_tester = _FakePipelineNodeTester()
    app.dependency_overrides[get_pipeline_node_tester] = lambda: fake_tester
    client = TestClient(app)

    response = client.post(
        "/admin/pipeline/test",
        files={"file": ("policy.md", b"# Policy\n\nEvidence is required.", "text/markdown")},
        data={"stage": "parse"},
    )

    assert response.status_code == 200
    assert response.json()["stage"] == "parse"
    assert response.json()["summary"]["block_count"] == 2
    assert fake_tester.stages == ["parse"]


def test_evaluation_cases_can_be_listed():
    client = TestClient(create_app())

    response = client.get("/admin/evaluation/cases")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "satellite-mode-exception"
    assert "question" in payload[0]


def test_evaluation_run_returns_case_results():
    app = create_app()
    app.dependency_overrides[get_chunk_index] = lambda: _FakeIndex()
    app.dependency_overrides[get_rag_answerer] = lambda: _FakeAnswerer()
    app.dependency_overrides[get_evaluation_history_store] = lambda: _FakeEvaluationHistoryStore()
    client = TestClient(app)

    response = client.post(
        "/admin/evaluation/run",
        json={
            "top_k": 1,
            "include_answers": True,
            "case_ids": ["satellite-mode-exception"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_cases"] == 1
    assert payload["results"][0]["case_id"] == "satellite-mode-exception"
    assert payload["results"][0]["contexts"][0]["file_name"] == "09_aquila_nested_corpus.json"


class _FakeIndex:
    def retrieve(self, query: str, *, top_k: int, metadata_filters=None):
        file_name = (
            "09_aquila_nested_corpus.json"
            if "14-day satellite-mode" in query
            else "policy.md"
        )
        return _retrieval_result(query=query, top_k=top_k, file_name=file_name)

    def stats(self):
        return PgVectorIndexStats(
            document_count=1,
            parent_chunk_count=1,
            child_chunk_count=1,
            embedding_model="fake-embedding",
            embedding_dimensions=3,
        )

    def list_documents(self, *, limit: int = 100, offset: int = 0):
        return [
            IndexedDocumentSummary(
                id="doc-1",
                title="Policy",
                file_name="policy.md",
                file_type="md",
                source_path="policy.md",
                parent_chunk_count=1,
                child_chunk_count=1,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                metadata={},
            )
        ]

    def clear(self):
        return None


class _FakePipelineNodeTester:
    def __init__(self) -> None:
        self.stages: list[str] = []

    def run(self, *, stage: str, file_path: Path) -> PipelineNodeTestResult:
        self.stages.append(stage)
        assert file_path.read_text(encoding="utf-8").startswith("# Policy")
        return PipelineNodeTestResult(
            stage="parse",
            duration_ms=1.25,
            summary={"file_name": file_path.name, "block_count": 2},
            preview=[{"block_type": "heading", "text": "Policy"}],
        )


class _FakeAnswerer:
    def answer(self, retrieval_result: RetrievalResult) -> RagAnswer:
        return RagAnswer(
            query=retrieval_result.query,
            answer="Policy P-004 mentions the exception [1].",
            llm_model="fake-llm",
            retrieval_result=retrieval_result,
            citations=[
                {
                    "rank": 1,
                    "file_name": "policy.md",
                    "child_chunk_id": "child-1",
                    "parent_chunk_id": "parent-1",
                }
            ],
        )


class _FakeTrace:
    id = "trace-1"


class _FakeTraceStore:
    def record_trace(self, **_):
        return _FakeTrace()


class _FakeEvaluationHistoryStore:
    def record_run(self, **_):
        return None


class _FakeIngestionJobStore:
    def __init__(self, job: IngestionJobRecord):
        self.job = job

    def list_jobs(self, *, limit: int = 20, offset: int = 0):
        return IngestionJobList(total=1, limit=limit, offset=offset, jobs=[self.job])

    def get_job(self, job_id: str):
        return self.job if job_id == self.job.id else None


class _FakeIngestionJobService:
    upload_root = Path(tempfile.gettempdir()) / "docu-search-test-uploads"

    def __init__(self):
        self.job = _ingestion_job(status="queued")
        self.store = _FakeIngestionJobStore(self.job)
        self.run_job_ids: list[str] = []

    def create_job(self, *, source_paths, options, source_kind="upload"):
        self.job = _ingestion_job(status="queued", source_paths=[str(path) for path in source_paths])
        self.store.job = self.job
        return self.job

    def run_job(self, job_id: str):
        self.run_job_ids.append(job_id)
        self.job = _ingestion_job(status="completed", indexed_child_count=1)
        self.store.job = self.job


def _ingestion_job(
    *,
    status: str,
    source_paths: list[str] | None = None,
    indexed_child_count: int = 0,
) -> IngestionJobRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return IngestionJobRecord(
        id="job-1",
        status=status,
        source_kind="upload",
        source_paths=source_paths or ["policy.md"],
        file_count=1,
        discovered_input_files=1 if status == "completed" else 0,
        parsed_document_count=1 if status == "completed" else 0,
        chunked_document_count=1 if status == "completed" else 0,
        parent_chunk_count=1 if status == "completed" else 0,
        child_chunk_count=indexed_child_count,
        indexed_child_count=indexed_child_count,
        failure_count=0,
        timings_ms={"total": 10.0} if status == "completed" else {},
        events=[],
        error_code=None,
        error_message=None,
        error_details={},
        options={"replace": True, "continue_on_error": True},
        created_at=now,
        updated_at=now,
        started_at=now if status != "queued" else None,
        completed_at=now if status in {"completed", "failed"} else None,
    )


def _retrieval_result(*, query: str, top_k: int, file_name: str = "policy.md") -> RetrievalResult:
    parent = ParentChunk(
        id="parent-1",
        document_id="doc-1",
        parent_index=0,
        text="P-004 password rotation exception context.",
        token_count=6,
        source_block_ids=["block-1"],
        source_refs=["lines:1-2"],
        parent_path=["Policy"],
    )
    child = ChildChunk(
        id="child-1",
        document_id="doc-1",
        parent_chunk_id=parent.id,
        child_index=0,
        text="P-004 satellite mode syncs within 14 days.",
        token_count=7,
        source_block_ids=["block-1"],
        source_refs=["lines:1-2"],
        parent_path=["Policy"],
    )
    return RetrievalResult(
        query=query,
        embedding_model="fake-embedding",
        top_k=top_k,
        results=[
            RetrievedChunk(
                rank=1,
                score=0.99,
                child_chunk=child,
                parent_chunk=parent,
                metadata={
                    "file_name": file_name,
                    "file_type": (
                        SupportedFileType.JSON
                        if file_name.endswith(".json")
                        else SupportedFileType.MARKDOWN
                    ),
                },
            )
        ],
        metadata={"indexed_document_count": 1},
    )
