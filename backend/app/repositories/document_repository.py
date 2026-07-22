"""
File: backend/app/repositories/document_repository.py
Purpose: Owns indexed document metadata persistence and retrieval.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.ingestion.chunking import ChunkedDocument
from app.integrations.database import connect_postgres
from app.repositories.chunk_repository import IndexedDocumentChunkSummary
from app.repositories.index_repository import IndexRepository, PgVectorIndexStats

if TYPE_CHECKING:
    from app.repositories.search_repository import PgVectorChunkIndex


@dataclass(frozen=True)
class IndexedDocumentSummary:
    id: str
    title: str
    file_name: str
    file_type: str
    source_path: str | None
    parent_chunk_count: int
    child_chunk_count: int
    created_at: datetime | None
    updated_at: datetime | None
    metadata: dict[str, Any]


class DocumentRepository:
    """Repository for document metadata and document-level lifecycle operations."""

    def __init__(
        self,
        *,
        database_url: str | None = None,
        index_repository: IndexRepository | None = None,
        index: "PgVectorChunkIndex | None" = None,
    ) -> None:
        self.index = index
        self._compatibility_index: Any | None = None
        if index is not None:
            if hasattr(index, "database_url") and hasattr(index, "index_repository"):
                database_url = database_url or index.database_url
                index_repository = index_repository or index.index_repository
            else:
                self._compatibility_index = index
                self.database_url = database_url
                self.index_repository = index_repository
                return
        self.database_url = database_url or get_settings().database.url
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for PostgreSQL pgvector indexing",
                code="DATABASE_URL_MISSING",
            )
        self.index_repository = index_repository

    def create_or_replace_document(
        self,
        *,
        connection: Any,
        document: ChunkedDocument,
    ) -> None:
        connection.execute(
            """
            INSERT INTO documents(
                id,
                title,
                file_name,
                file_type,
                source_path,
                metadata,
                updated_at
            )
            VALUES(%s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT(id) DO UPDATE SET
                title = EXCLUDED.title,
                file_name = EXCLUDED.file_name,
                file_type = EXCLUDED.file_type,
                source_path = EXCLUDED.source_path,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            """,
            (
                document.document_id,
                document.title,
                document.file_name,
                str(document.file_type),
                document.source_path,
                self._dumps_json(document.metadata),
            ),
        )

    def list_documents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IndexedDocumentSummary]:
        if self._compatibility_index is not None:
            return self._compatibility_index.list_documents(limit=limit, offset=offset)

        if limit < 1 or limit > 500:
            raise RetrievalError(
                "limit must be between 1 and 500",
                code="INVALID_DOCUMENT_LIST_LIMIT",
                details={"limit": limit},
            )
        if offset < 0:
            raise RetrievalError(
                "offset cannot be negative",
                code="INVALID_DOCUMENT_LIST_OFFSET",
                details={"offset": offset},
            )

        self._initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.file_name,
                    d.file_type,
                    d.source_path,
                    d.metadata,
                    d.created_at,
                    d.updated_at,
                    COALESCE(pc.parent_chunk_count, 0) AS parent_chunk_count,
                    COALESCE(cc.child_chunk_count, 0) AS child_chunk_count
                FROM documents d
                LEFT JOIN (
                    SELECT document_id, COUNT(*) AS parent_chunk_count
                    FROM parent_chunks
                    GROUP BY document_id
                ) pc ON pc.document_id = d.id
                LEFT JOIN (
                    SELECT document_id, COUNT(*) AS child_chunk_count
                    FROM child_chunks
                    GROUP BY document_id
                ) cc ON cc.document_id = d.id
                ORDER BY d.file_name, d.id
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()

        return [self.document_summary_from_row(row) for row in rows]

    def get_document(self, document_id: str) -> IndexedDocumentSummary | None:
        if self._compatibility_index is not None:
            return self._compatibility_index.get_document(document_id)

        self._initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    d.id,
                    d.title,
                    d.file_name,
                    d.file_type,
                    d.source_path,
                    d.metadata,
                    d.created_at,
                    d.updated_at,
                    COALESCE(pc.parent_chunk_count, 0) AS parent_chunk_count,
                    COALESCE(cc.child_chunk_count, 0) AS child_chunk_count
                FROM documents d
                LEFT JOIN (
                    SELECT document_id, COUNT(*) AS parent_chunk_count
                    FROM parent_chunks
                    GROUP BY document_id
                ) pc ON pc.document_id = d.id
                LEFT JOIN (
                    SELECT document_id, COUNT(*) AS child_chunk_count
                    FROM child_chunks
                    GROUP BY document_id
                ) cc ON cc.document_id = d.id
                WHERE d.id = %s
                """,
                (document_id,),
            ).fetchone()

        return self.document_summary_from_row(row) if row else None

    def delete_document(self, document_id: str, *, connection: Any | None = None) -> bool:
        if self._compatibility_index is not None:
            return self._compatibility_index.delete_document(document_id)

        if connection is not None:
            return self.delete_document_with_connection(
                connection=connection,
                document_id=document_id,
            )

        self._initialize()
        with self._connect() as owned_connection:
            return self.delete_document_with_connection(
                connection=owned_connection,
                document_id=document_id,
            )

    def delete_document_with_connection(self, *, connection: Any, document_id: str) -> bool:
        row = connection.execute(
            "DELETE FROM documents WHERE id = %s RETURNING id",
            (document_id,),
        ).fetchone()
        return row is not None

    def resolve_source_metadata(
        self,
        document_id: str,
    ) -> IndexedDocumentSummary | None:
        return self.get_document(document_id)

    def stats(self) -> PgVectorIndexStats:
        if self._compatibility_index is not None:
            return self._compatibility_index.stats()

        return self._index_repository().stats()

    def clear_index(self) -> PgVectorIndexStats:
        if self._compatibility_index is not None:
            self._compatibility_index.clear()
            return self._compatibility_index.stats()

        index_repository = self._index_repository()
        index_repository.clear()
        return index_repository.stats()

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[int, list[IndexedDocumentChunkSummary]]:
        if self._compatibility_index is not None:
            return self._compatibility_index.list_document_chunks(
                document_id,
                limit=limit,
                offset=offset,
            )

        from app.repositories.chunk_repository import ChunkRepository

        index_repository = self._index_repository()
        return ChunkRepository(
            database_url=self.database_url,
            embedding_provider=index_repository.embedding_provider,
            index_repository=index_repository,
        ).list_document_chunks(document_id, limit=limit, offset=offset)

    def document_summary_from_row(self, row: dict[str, Any]) -> IndexedDocumentSummary:
        return IndexedDocumentSummary(
            id=row["id"],
            title=row["title"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            source_path=row["source_path"],
            parent_chunk_count=int(row["parent_chunk_count"]),
            child_chunk_count=int(row["child_chunk_count"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=self._loads_json(row["metadata"]),
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

    def _index_repository(self) -> IndexRepository:
        if self.index_repository is None:
            raise RetrievalError(
                "Index repository is required for index-level document operations",
                code="INDEX_REPOSITORY_MISSING",
            )
        return self.index_repository

    def _dumps_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _loads_json(self, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value)

        return value
