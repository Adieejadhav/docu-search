"""
File: backend/app/repositories/chunk_repository.py
Purpose: Owns parent/child chunk persistence and chunk listing for indexed documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.ingestion.chunking import ChildChunk, ChunkedDocument, ParentChunk
from app.integrations.database import connect_postgres
from app.integrations.embeddings import EmbeddingProvider

if TYPE_CHECKING:
    from app.repositories.index_repository import IndexRepository
    from app.repositories.search_repository import PgVectorChunkIndex


@dataclass(frozen=True)
class IndexedDocumentChunkSummary:
    child_chunk_id: str
    parent_chunk_id: str
    child_index: int
    parent_index: int
    child_text: str
    parent_text: str
    child_token_count: int
    parent_token_count: int
    source_refs: list[str]
    parent_path: list[str]
    metadata: dict[str, Any]
    created_at: datetime | None


class ChunkRepository:
    """Repository for parent chunks, child chunks, and child embeddings."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        embedding_provider: EmbeddingProvider,
        index_repository: "IndexRepository | None" = None,
        index: "PgVectorChunkIndex | None" = None,
    ) -> None:
        if index is not None:
            database_url = database_url or index.database_url
            index_repository = index_repository or index.index_repository
        self.database_url = database_url or get_settings().database.url
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for PostgreSQL pgvector indexing",
                code="DATABASE_URL_MISSING",
            )
        self.embedding_provider = embedding_provider
        self.index_repository = index_repository

    def save_parent_chunks(self, *, connection: Any, document: ChunkedDocument) -> None:
        for parent_chunk in document.parent_chunks:
            connection.execute(
                """
                INSERT INTO parent_chunks(
                    id,
                    document_id,
                    parent_index,
                    text,
                    token_count,
                    source_block_ids,
                    source_refs,
                    parent_path,
                    metadata,
                    chunk_json,
                    updated_at
                )
                VALUES(%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                       %s::jsonb, %s::jsonb, NOW())
                ON CONFLICT(id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    parent_index = EXCLUDED.parent_index,
                    text = EXCLUDED.text,
                    token_count = EXCLUDED.token_count,
                    source_block_ids = EXCLUDED.source_block_ids,
                    source_refs = EXCLUDED.source_refs,
                    parent_path = EXCLUDED.parent_path,
                    metadata = EXCLUDED.metadata,
                    chunk_json = EXCLUDED.chunk_json,
                    updated_at = NOW()
                """,
                (
                    parent_chunk.id,
                    document.document_id,
                    parent_chunk.parent_index,
                    parent_chunk.text,
                    parent_chunk.token_count,
                    self._dumps_json(parent_chunk.source_block_ids),
                    self._dumps_json(parent_chunk.source_refs),
                    self._dumps_json(parent_chunk.parent_path),
                    self._dumps_json(parent_chunk.metadata),
                    self._dumps_model(parent_chunk),
                ),
            )

    def save_child_chunks(self, *, connection: Any, document: ChunkedDocument) -> int:
        vectors = self.embedding_provider.embed_texts(
            [child_chunk.text for child_chunk in document.child_chunks]
        )
        for child_chunk, vector in zip(document.child_chunks, vectors, strict=True):
            connection.execute(
                """
                INSERT INTO child_chunks(
                    id,
                    document_id,
                    parent_chunk_id,
                    child_index,
                    text,
                    token_count,
                    source_block_ids,
                    source_refs,
                    parent_path,
                    metadata,
                    chunk_json,
                    updated_at
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb,
                       %s::jsonb, %s::jsonb, NOW())
                ON CONFLICT(id) DO UPDATE SET
                    document_id = EXCLUDED.document_id,
                    parent_chunk_id = EXCLUDED.parent_chunk_id,
                    child_index = EXCLUDED.child_index,
                    text = EXCLUDED.text,
                    token_count = EXCLUDED.token_count,
                    source_block_ids = EXCLUDED.source_block_ids,
                    source_refs = EXCLUDED.source_refs,
                    parent_path = EXCLUDED.parent_path,
                    metadata = EXCLUDED.metadata,
                    chunk_json = EXCLUDED.chunk_json,
                    updated_at = NOW()
                """,
                (
                    child_chunk.id,
                    document.document_id,
                    child_chunk.parent_chunk_id,
                    child_chunk.child_index,
                    child_chunk.text,
                    child_chunk.token_count,
                    self._dumps_json(child_chunk.source_block_ids),
                    self._dumps_json(child_chunk.source_refs),
                    self._dumps_json(child_chunk.parent_path),
                    self._dumps_json(child_chunk.metadata),
                    self._dumps_model(child_chunk),
                ),
            )
            connection.execute(
                """
                INSERT INTO child_embeddings(
                    child_chunk_id,
                    embedding,
                    embedding_model,
                    embedding_dimensions,
                    updated_at
                )
                VALUES(%s, %s::vector, %s, %s, NOW())
                ON CONFLICT(child_chunk_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    embedding_dimensions = EXCLUDED.embedding_dimensions,
                    updated_at = NOW()
                """,
                (
                    child_chunk.id,
                    self._vector_to_sql(vector),
                    self.embedding_provider.name,
                    self.embedding_provider.dimensions,
                ),
            )

        return len(document.child_chunks)

    def delete_chunks_for_document(self, *, connection: Any, document_id: str) -> None:
        connection.execute(
            """
            DELETE FROM child_embeddings
            WHERE child_chunk_id IN (
                SELECT id FROM child_chunks WHERE document_id = %s
            )
            """,
            (document_id,),
        )
        connection.execute("DELETE FROM child_chunks WHERE document_id = %s", (document_id,))
        connection.execute("DELETE FROM parent_chunks WHERE document_id = %s", (document_id,))

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[IndexedDocumentChunkSummary]]:
        if limit < 1 or limit > 500:
            raise RetrievalError(
                "limit must be between 1 and 500",
                code="INVALID_DOCUMENT_CHUNK_LIMIT",
                details={"limit": limit},
            )
        if offset < 0:
            raise RetrievalError(
                "offset cannot be negative",
                code="INVALID_DOCUMENT_CHUNK_OFFSET",
                details={"offset": offset},
            )

        self._initialize()
        with self._connect() as connection:
            return self.list_document_chunks_with_connection(
                connection=connection,
                document_id=document_id,
                limit=limit,
                offset=offset,
            )

    def list_document_chunks_with_connection(
        self,
        *,
        connection: Any,
        document_id: str,
        limit: int,
        offset: int,
    ) -> tuple[int, list[IndexedDocumentChunkSummary]]:
        total_row = connection.execute(
            "SELECT COUNT(*) AS count FROM child_chunks WHERE document_id = %s",
            (document_id,),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT
                cc.id AS child_chunk_id,
                pc.id AS parent_chunk_id,
                cc.child_index,
                pc.parent_index,
                cc.text AS child_text,
                pc.text AS parent_text,
                cc.token_count AS child_token_count,
                pc.token_count AS parent_token_count,
                cc.source_refs,
                cc.parent_path,
                cc.metadata,
                cc.created_at
            FROM child_chunks cc
            JOIN parent_chunks pc ON pc.id = cc.parent_chunk_id
            WHERE cc.document_id = %s
            ORDER BY pc.parent_index, cc.child_index
            LIMIT %s OFFSET %s
            """,
            (document_id, limit, offset),
        ).fetchall()

        return (
            int(total_row["count"]),
            [self.document_chunk_summary_from_row(row) for row in rows],
        )

    def document_chunk_summary_from_row(
        self,
        row: dict[str, Any],
    ) -> IndexedDocumentChunkSummary:
        return IndexedDocumentChunkSummary(
            child_chunk_id=row["child_chunk_id"],
            parent_chunk_id=row["parent_chunk_id"],
            child_index=int(row["child_index"]),
            parent_index=int(row["parent_index"]),
            child_text=row["child_text"],
            parent_text=row["parent_text"],
            child_token_count=int(row["child_token_count"]),
            parent_token_count=int(row["parent_token_count"]),
            source_refs=self._loads_json(row["source_refs"]),
            parent_path=self._loads_json(row["parent_path"]),
            metadata=self._loads_json(row["metadata"]),
            created_at=row["created_at"],
        )

    def _initialize(self) -> None:
        if self.index_repository is not None:
            self.index_repository.initialize()

    def _connect(self) -> Any:
        if self.index_repository is not None:
            return self.index_repository.connect()
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for PostgreSQL indexing"
            ),
        )

    def _vector_to_sql(self, vector: list[float]) -> str:
        if self.index_repository is not None:
            return self.index_repository.vector_to_sql(vector)
        if len(vector) != self.embedding_provider.dimensions:
            raise RetrievalError(
                "Embedding vector has unexpected dimensions",
                code="INVALID_EMBEDDING_DIMENSIONS",
                details={
                    "expected_dimensions": self.embedding_provider.dimensions,
                    "actual_dimensions": len(vector),
                },
            )
        return "[" + ",".join(f"{float(value):.12g}" for value in vector) + "]"

    def _dumps_model(self, value: ChildChunk | ParentChunk) -> str:
        return self._dumps_json(value.model_dump(mode="json"))

    def _dumps_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _loads_json(self, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)

        return value
