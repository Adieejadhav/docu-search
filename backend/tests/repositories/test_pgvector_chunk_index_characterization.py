from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.exceptions import RetrievalError
from app.ingestion.chunking import ChildChunk, ChunkedDocument, ParentChunk
from app.integrations.embeddings import EmbeddingProvider
from app.repositories import PgVectorChunkIndex


def test_index_documents_preserves_progress_embedding_and_persistence_order():
    connection = _FakeConnection()
    index = PgVectorChunkIndex(
        database_url="postgresql://user:secret@localhost/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )
    index.initialize = lambda: None  # type: ignore[method-assign]
    index._connect = lambda: connection  # type: ignore[method-assign]
    events: list[dict[str, Any]] = []

    indexed_count = index.index_documents(
        [_chunked_document()],
        replace=True,
        progress_callback=events.append,
    )

    assert indexed_count == 1
    assert index.embedding_provider.embedded_text_batches == [["Child policy text"]]
    assert [event["status"] for event in events] == ["started", "completed"]
    assert events[0]["child_chunks"] == 1
    assert events[1]["indexed_child_chunks"] == 1
    assert [operation.split(" WHERE ", 1)[0] for operation in connection.sql_operations[:4]] == [
        "DELETE FROM child_embeddings",
        "DELETE FROM child_chunks",
        "DELETE FROM parent_chunks",
        "DELETE FROM documents",
    ]
    assert any(sql.startswith("INSERT INTO documents") for sql in connection.sql_operations)
    assert any(sql.startswith("INSERT INTO parent_chunks") for sql in connection.sql_operations)
    assert any(sql.startswith("INSERT INTO child_chunks") for sql in connection.sql_operations)
    assert any(sql.startswith("INSERT INTO child_embeddings") for sql in connection.sql_operations)


def test_retrieve_preserves_validation_mapping_stats_and_redacted_metadata():
    connection = _FakeConnection()
    index = PgVectorChunkIndex(
        database_url="postgresql://user:secret@localhost/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )
    index.index_repository.initialize = lambda: None  # type: ignore[method-assign]
    index.index_repository.connect = lambda: connection  # type: ignore[method-assign]
    index.search_repository.search_vector_rows = lambda **_: [_retrieval_row("child-1", 0.8, 0.0)]  # type: ignore[method-assign]
    index.search_repository.search_lexical_rows = lambda **_: [_retrieval_row("child-1", 0.7, 0.2)]  # type: ignore[method-assign]

    result = index.retrieve(
        "satellite policy",
        top_k=1,
        metadata_filters={"file_name": "policy.md"},
    )

    assert index.embedding_provider.embedded_texts == ["satellite policy"]
    assert result.query == "satellite policy"
    assert result.embedding_model == "fake-embedding"
    assert result.top_k == 1
    assert result.metadata["database_url"] == "postgresql://***@localhost/db"
    assert result.metadata["indexed_document_count"] == 2
    assert result.metadata["indexed_parent_chunk_count"] == 3
    assert result.metadata["indexed_child_chunk_count"] == 4
    assert result.metadata["retrieval_mode"] == "hybrid_vector_full_text"
    assert result.results[0].rank == 1
    assert result.results[0].child_chunk.id == "child-1"
    assert result.results[0].parent_chunk.id == "parent-1"
    assert result.results[0].metadata["vector_record_id"] == "child-1"


def test_retrieve_rejects_empty_query_and_invalid_top_k():
    index = PgVectorChunkIndex(
        database_url="postgresql://example/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )

    with pytest.raises(RetrievalError) as empty_error:
        index.retrieve("   ")
    with pytest.raises(RetrievalError) as top_k_error:
        index.retrieve("policy", top_k=0)

    assert empty_error.value.code == "EMPTY_RETRIEVAL_QUERY"
    assert top_k_error.value.code == "INVALID_TOP_K"


def test_document_listing_chunks_delete_and_stats_mapping_are_preserved():
    connection = _FakeConnection()
    index = PgVectorChunkIndex(
        database_url="postgresql://example/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )
    index.initialize = lambda: None  # type: ignore[method-assign]
    index._connect = lambda: connection  # type: ignore[method-assign]
    index.index_repository.initialize = lambda: None  # type: ignore[method-assign]
    index.index_repository.connect = lambda: connection  # type: ignore[method-assign]

    documents = index.list_documents(limit=10, offset=0)
    document = index.get_document("doc-1")
    total_chunks, chunks = index.list_document_chunks("doc-1", limit=10, offset=0)
    deleted = index.delete_document("doc-1")
    stats = index.stats()

    assert documents[0].id == "doc-1"
    assert document is not None
    assert document.file_name == "policy.md"
    assert total_chunks == 1
    assert chunks[0].child_chunk_id == "child-1"
    assert chunks[0].parent_text == "Parent policy text"
    assert deleted is True
    assert stats.document_count == 2
    assert stats.parent_chunk_count == 3
    assert stats.child_chunk_count == 4
    assert stats.embedding_model == "fake-embedding"
    assert stats.embedding_dimensions == 3


def _chunked_document() -> ChunkedDocument:
    parent = ParentChunk(
        id="parent-1",
        document_id="doc-1",
        parent_index=0,
        text="Parent policy text",
        token_count=3,
        source_block_ids=["block-1"],
        source_refs=["lines:1-2"],
        parent_path=["Policy"],
        metadata={"section": "Policy"},
    )
    child = ChildChunk(
        id="child-1",
        document_id="doc-1",
        parent_chunk_id="parent-1",
        child_index=0,
        text="Child policy text",
        token_count=3,
        source_block_ids=["block-1"],
        source_refs=["lines:1-2"],
        parent_path=["Policy"],
        metadata={"section": "Policy"},
    )
    return ChunkedDocument(
        document_id="doc-1",
        title="Policy",
        file_name="policy.md",
        file_type="md",
        source_path="C:/docs/policy.md",
        parent_chunks=[parent],
        child_chunks=[child],
        metadata={"owner": "security"},
    )


def _retrieval_row(child_id: str, vector_score: float, lexical_score: float) -> dict[str, Any]:
    document = _chunked_document()
    return {
        "child_id": child_id,
        "child_json": document.child_chunks[0].model_dump(mode="json"),
        "parent_json": document.parent_chunks[0].model_dump(mode="json"),
        "file_name": "policy.md",
        "file_type": "md",
        "vector_score": vector_score,
        "lexical_score": lexical_score,
    }


class _FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.embedded_texts: list[str] = []
        self.embedded_text_batches: list[list[str]] = []

    @property
    def name(self) -> str:
        return "fake-embedding"

    @property
    def dimensions(self) -> int:
        return 3

    def embed_text(self, text: str) -> list[float]:
        self.embedded_texts.append(text)
        return [1.0, 0.0, 0.0]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.embedded_text_batches.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


class _FakeCursor:
    def __init__(
        self,
        *,
        rows: list[dict[str, Any]] | None = None,
        row: dict[str, Any] | None = None,
    ) -> None:
        self._rows = rows or []
        self._row = row

    def fetchone(self) -> dict[str, Any] | None:
        if self._row is not None:
            return self._row
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows

    def __iter__(self):
        return iter(self._rows)


class _FakeConnection:
    def __init__(self) -> None:
        self.sql_operations: list[str] = []

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, params: Any = None) -> _FakeCursor:
        operation = " ".join(sql.strip().split())
        self.sql_operations.append(operation)
        if operation == "SELECT key, value FROM index_metadata":
            return _FakeCursor(
                rows=[
                    {"key": "embedding_model", "value": "fake-embedding"},
                    {"key": "embedding_dimensions", "value": "3"},
                ]
            )
        if operation.startswith("SELECT COUNT(*) AS count FROM documents"):
            return _FakeCursor(row={"count": 2})
        if operation.startswith("SELECT COUNT(*) AS count FROM parent_chunks"):
            return _FakeCursor(row={"count": 3})
        if operation.startswith("SELECT COUNT(*) AS count FROM child_chunks WHERE document_id"):
            return _FakeCursor(row={"count": 1})
        if operation.startswith("SELECT COUNT(*) AS count FROM child_chunks"):
            return _FakeCursor(row={"count": 4})
        if operation.startswith("SELECT d.id"):
            rows = [_document_row()]
            return _FakeCursor(row=rows[0], rows=rows)
        if operation.startswith("SELECT cc.id AS child_chunk_id"):
            return _FakeCursor(rows=[_document_chunk_row()])
        if operation.startswith("DELETE FROM documents WHERE id"):
            return _FakeCursor(row={"id": "doc-1"})
        return _FakeCursor()


def _document_row() -> dict[str, Any]:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "id": "doc-1",
        "title": "Policy",
        "file_name": "policy.md",
        "file_type": "md",
        "source_path": "C:/docs/policy.md",
        "metadata": {"owner": "security"},
        "created_at": now,
        "updated_at": now,
        "parent_chunk_count": 1,
        "child_chunk_count": 1,
    }


def _document_chunk_row() -> dict[str, Any]:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return {
        "child_chunk_id": "child-1",
        "parent_chunk_id": "parent-1",
        "child_index": 0,
        "parent_index": 0,
        "child_text": "Child policy text",
        "parent_text": "Parent policy text",
        "child_token_count": 3,
        "parent_token_count": 3,
        "source_refs": ["lines:1-2"],
        "parent_path": ["Policy"],
        "metadata": {"section": "Policy"},
        "created_at": now,
    }
