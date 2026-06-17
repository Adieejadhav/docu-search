from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_chunk_index, get_database_url, get_rag_answerer
from app.core.constants import SupportedFileType
from app.db import DatabaseHealth
from app.indexing import IndexedDocumentSummary, PgVectorIndexStats
from app.ingestion.chunking import ChildChunk, ParentChunk
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


class _FakeIndex:
    def retrieve(self, query: str, *, top_k: int, metadata_filters=None):
        return _retrieval_result(query=query, top_k=top_k)

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


def _retrieval_result(*, query: str, top_k: int) -> RetrievalResult:
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
                metadata={"file_name": "policy.md", "file_type": SupportedFileType.MARKDOWN},
            )
        ],
        metadata={"indexed_document_count": 1},
    )
