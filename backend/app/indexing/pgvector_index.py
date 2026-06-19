"""
File: backend/app/indexing/pgvector_index.py
Purpose: Provides production PostgreSQL + pgvector indexing and retrieval.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import os
import re
from time import perf_counter
from typing import Any

from app.core.exceptions import RetrievalError
from app.core.env import load_environment
from app.db.connection import connect_postgres
from app.ingestion.chunking import ChildChunk, ChunkedDocument, ParentChunk
from app.embeddings import (
    EmbeddingProvider,
    EmbeddingVector,
    LocalSentenceTransformerEmbeddingProvider,
)
from app.search.retrieval import RetrievedChunk, RetrievalResult

IndexProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class PgVectorIndexStats:
    document_count: int
    parent_chunk_count: int
    child_chunk_count: int
    embedding_model: str | None
    embedding_dimensions: int | None


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


class PgVectorChunkIndex:
    """
    Production chunk/vector index backed by PostgreSQL and pgvector.
    """

    SCHEMA_VERSION = 1
    MIN_HYBRID_CANDIDATES = 50
    MAX_HYBRID_CANDIDATES = 200
    DEFAULT_HYBRID_VECTOR_WEIGHT = 0.62
    DEFAULT_HYBRID_LEXICAL_WEIGHT = 0.30
    DEFAULT_HYBRID_PHRASE_WEIGHT = 0.08

    def __init__(
        self,
        *,
        database_url: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        load_environment()
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for PostgreSQL pgvector indexing",
                code="DATABASE_URL_MISSING",
            )

        self.embedding_provider = (
            embedding_provider or LocalSentenceTransformerEmbeddingProvider()
        )
        self.hybrid_vector_weight = configured_float(
            "HYBRID_VECTOR_WEIGHT",
            self.DEFAULT_HYBRID_VECTOR_WEIGHT,
        )
        self.hybrid_lexical_weight = configured_float(
            "HYBRID_LEXICAL_WEIGHT",
            self.DEFAULT_HYBRID_LEXICAL_WEIGHT,
        )
        self.hybrid_phrase_weight = configured_float(
            "HYBRID_PHRASE_WEIGHT",
            self.DEFAULT_HYBRID_PHRASE_WEIGHT,
        )

    def initialize(self) -> None:
        with self._connect() as connection:
            self._lock_schema_initialization(connection)
            self._create_schema(connection)
            self._validate_or_set_index_metadata(connection)

    def clear(self) -> None:
        self.initialize()
        with self._connect() as connection:
            for table_name in (
                "child_embeddings",
                "child_chunks",
                "parent_chunks",
                "documents",
            ):
                connection.execute(f"DELETE FROM {table_name}")

    def index_documents(
        self,
        documents: list[ChunkedDocument],
        *,
        replace: bool = True,
        progress_callback: IndexProgressCallback | None = None,
    ) -> int:
        self.initialize()
        with self._connect() as connection:
            if replace:
                for document in documents:
                    self._delete_document(connection, document.document_id)

            indexed_child_count = 0
            document_count = len(documents)
            for document_index, document in enumerate(documents, start=1):
                document_start = perf_counter()
                if progress_callback is not None:
                    progress_callback(
                        {
                            "status": "started",
                            "document": document,
                            "document_index": document_index,
                            "document_count": document_count,
                            "child_chunks": len(document.child_chunks),
                        }
                    )

                self._insert_document(connection, document)
                self._insert_parent_chunks(connection, document)
                indexed_document_children = self._insert_child_chunks(
                    connection,
                    document,
                )
                indexed_child_count += indexed_document_children

                if progress_callback is not None:
                    progress_callback(
                        {
                            "status": "completed",
                            "document": document,
                            "document_index": document_index,
                            "document_count": document_count,
                            "child_chunks": len(document.child_chunks),
                            "indexed_child_chunks": indexed_document_children,
                            "duration_ms": self._duration_ms(document_start),
                        }
                    )

            return indexed_child_count

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        metadata_filters: dict[str, Any] | None = None,
    ) -> RetrievalResult:
        if not query.strip():
            raise RetrievalError(
                "Retrieval query cannot be empty",
                code="EMPTY_RETRIEVAL_QUERY",
            )

        if top_k < 1:
            raise RetrievalError(
                "top_k must be greater than zero",
                code="INVALID_TOP_K",
                details={"top_k": top_k},
            )

        self.initialize()
        query_vector = self.embedding_provider.embed_text(query)
        query_vector_text = self._vector_to_sql(query_vector)

        with self._connect() as connection:
            vector_rows = self._search_vector_rows(
                connection=connection,
                query_vector_text=query_vector_text,
                query=query,
                top_k=self._candidate_limit(top_k),
                metadata_filters=metadata_filters,
            )
            lexical_rows = self._search_lexical_rows(
                connection=connection,
                query_vector_text=query_vector_text,
                query=query,
                top_k=self._candidate_limit(top_k),
                metadata_filters=metadata_filters,
            )
            rows = self._merge_and_rerank_rows(
                query=query,
                vector_rows=vector_rows,
                lexical_rows=lexical_rows,
                top_k=top_k,
            )
            results = [
                self._retrieved_chunk_from_row(row=row, rank=rank)
                for rank, row in enumerate(rows, start=1)
            ]
            stats = self.stats(connection=connection)

        return RetrievalResult(
            query=query,
            embedding_model=self.embedding_provider.name,
            top_k=top_k,
            results=results,
            metadata={
                "database_url": self._redacted_database_url(),
                "indexed_document_count": stats.document_count,
                "indexed_parent_chunk_count": stats.parent_chunk_count,
                "indexed_child_chunk_count": stats.child_chunk_count,
                "retrieval_mode": "hybrid_vector_full_text",
                "hybrid_weights": {
                    "vector": self._hybrid_vector_weight(),
                    "lexical": self._hybrid_lexical_weight(),
                    "phrase": self._hybrid_phrase_weight(),
                },
            },
        )

    def stats(self, *, connection: Any | None = None) -> PgVectorIndexStats:
        if connection is not None:
            return self._stats(connection)

        self.initialize()
        with self._connect() as owned_connection:
            return self._stats(owned_connection)

    def list_documents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IndexedDocumentSummary]:
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

        self.initialize()
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

        return [self._document_summary_from_row(row) for row in rows]

    def get_document(self, document_id: str) -> IndexedDocumentSummary | None:
        self.initialize()
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

        return self._document_summary_from_row(row) if row else None

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

        self.initialize()
        with self._connect() as connection:
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
            [self._document_chunk_summary_from_row(row) for row in rows],
        )

    def delete_document(self, document_id: str) -> bool:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "DELETE FROM documents WHERE id = %s RETURNING id",
                (document_id,),
            ).fetchone()

        return row is not None

    def _connect(self) -> Any:
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for PostgreSQL indexing"
            ),
        )

    def _lock_schema_initialization(self, connection: Any) -> None:
        connection.execute("SELECT pg_advisory_xact_lock(420240519826)")

    def _create_schema(self, connection: Any) -> None:
        dimensions = self.embedding_provider.dimensions
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS index_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                source_path TEXT,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS parent_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                parent_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                source_block_ids JSONB NOT NULL,
                source_refs JSONB NOT NULL,
                parent_path JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                chunk_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS child_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                parent_chunk_id TEXT NOT NULL REFERENCES parent_chunks(id) ON DELETE CASCADE,
                child_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                token_count INTEGER NOT NULL,
                source_block_ids JSONB NOT NULL,
                source_refs JSONB NOT NULL,
                parent_path JSONB NOT NULL,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                chunk_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS child_embeddings (
                child_chunk_id TEXT PRIMARY KEY
                    REFERENCES child_chunks(id) ON DELETE CASCADE,
                embedding vector({dimensions}) NOT NULL,
                embedding_model TEXT NOT NULL,
                embedding_dimensions INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_parent_chunks_document_id
                ON parent_chunks(document_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_child_chunks_document_id
                ON child_chunks(document_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_child_chunks_parent_chunk_id
                ON child_chunks(parent_chunk_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_file_name
                ON documents(file_name)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_file_type
                ON documents(file_type)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_child_embeddings_embedding_hnsw
                ON child_embeddings
                USING hnsw (embedding vector_cosine_ops)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_child_chunks_text_fts
                ON child_chunks
                USING gin (to_tsvector('english', text))
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_parent_chunks_text_fts
                ON parent_chunks
                USING gin (to_tsvector('english', text))
            """
        )

    def _validate_or_set_index_metadata(self, connection: Any) -> None:
        metadata = self._metadata(connection)
        existing_dimensions = metadata.get("embedding_dimensions")
        existing_model = metadata.get("embedding_model")

        if existing_dimensions and int(existing_dimensions) != self.embedding_provider.dimensions:
            raise RetrievalError(
                "Existing pgvector index uses different embedding dimensions",
                code="PGVECTOR_DIMENSION_MISMATCH",
                details={
                    "existing_dimensions": int(existing_dimensions),
                    "requested_dimensions": self.embedding_provider.dimensions,
                },
            )

        if existing_model and existing_model != self.embedding_provider.name:
            raise RetrievalError(
                "Existing pgvector index uses a different embedding model",
                code="PGVECTOR_EMBEDDING_MODEL_MISMATCH",
                details={
                    "existing_model": existing_model,
                    "requested_model": self.embedding_provider.name,
                },
            )

        values = {
            "schema_version": str(self.SCHEMA_VERSION),
            "embedding_model": self.embedding_provider.name,
            "embedding_dimensions": str(self.embedding_provider.dimensions),
        }
        for key, value in values.items():
            connection.execute(
                """
                INSERT INTO index_metadata(key, value)
                VALUES(%s, %s)
                ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value
                """,
                (key, value),
            )

    def _delete_document(self, connection: Any, document_id: str) -> None:
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
        connection.execute("DELETE FROM documents WHERE id = %s", (document_id,))

    def _insert_document(self, connection: Any, document: ChunkedDocument) -> None:
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

    def _insert_parent_chunks(self, connection: Any, document: ChunkedDocument) -> None:
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

    def _insert_child_chunks(self, connection: Any, document: ChunkedDocument) -> int:
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

    def _search_vector_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        where_parts: list[str] = []
        filter_params: list[Any] = []

        for field_name in ("file_name", "file_type", "document_id"):
            if metadata_filters and field_name in metadata_filters:
                if field_name == "document_id":
                    where_parts.append("cc.document_id = %s")
                else:
                    where_parts.append(f"d.{field_name} = %s")
                filter_params.append(metadata_filters[field_name])

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        return list(
            connection.execute(
                f"""
                SELECT
                    cc.id AS child_id,
                    cc.chunk_json AS child_json,
                    pc.chunk_json AS parent_json,
                    d.file_name AS file_name,
                    d.file_type AS file_type,
                    1 - (ce.embedding <=> %s::vector) AS vector_score,
                    ts_rank_cd(
                        to_tsvector('english', cc.text || ' ' || pc.text || ' ' || d.file_name),
                        websearch_to_tsquery('english', %s)
                    ) AS lexical_score
                FROM child_chunks cc
                JOIN child_embeddings ce ON ce.child_chunk_id = cc.id
                JOIN parent_chunks pc ON pc.id = cc.parent_chunk_id
                JOIN documents d ON d.id = cc.document_id
                {where_clause}
                ORDER BY ce.embedding <=> %s::vector
                LIMIT %s
                """,
                [query_vector_text, query, *filter_params, query_vector_text, top_k],
            )
        )

    def _search_lexical_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        where_parts: list[str] = [
            """
            (
                to_tsvector('english', cc.text) @@ websearch_to_tsquery('english', %s)
                OR to_tsvector('english', pc.text) @@ websearch_to_tsquery('english', %s)
                OR to_tsvector('english', d.file_name) @@ websearch_to_tsquery('english', %s)
            )
            """
        ]
        filter_params: list[Any] = [query, query, query]

        for field_name in ("file_name", "file_type", "document_id"):
            if metadata_filters and field_name in metadata_filters:
                if field_name == "document_id":
                    where_parts.append("cc.document_id = %s")
                else:
                    where_parts.append(f"d.{field_name} = %s")
                filter_params.append(metadata_filters[field_name])

        where_clause = f"WHERE {' AND '.join(where_parts)}"
        return list(
            connection.execute(
                f"""
                SELECT
                    cc.id AS child_id,
                    cc.chunk_json AS child_json,
                    pc.chunk_json AS parent_json,
                    d.file_name AS file_name,
                    d.file_type AS file_type,
                    1 - (ce.embedding <=> %s::vector) AS vector_score,
                    ts_rank_cd(
                        to_tsvector('english', cc.text || ' ' || pc.text || ' ' || d.file_name),
                        websearch_to_tsquery('english', %s)
                    ) AS lexical_score
                FROM child_chunks cc
                JOIN child_embeddings ce ON ce.child_chunk_id = cc.id
                JOIN parent_chunks pc ON pc.id = cc.parent_chunk_id
                JOIN documents d ON d.id = cc.document_id
                {where_clause}
                ORDER BY lexical_score DESC, vector_score DESC
                LIMIT %s
                """,
                [query_vector_text, query, *filter_params, top_k],
            )
        )

    def _merge_and_rerank_rows(
        self,
        *,
        query: str,
        vector_rows: list[dict[str, Any]],
        lexical_rows: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        has_lexical_hits = False

        for source_name, rows in (("vector", vector_rows), ("lexical", lexical_rows)):
            for source_rank, row in enumerate(rows, start=1):
                row_key = str(row["child_id"])
                existing = merged.get(row_key)
                if existing is None:
                    existing = dict(row)
                    existing["vector_rank"] = None
                    existing["lexical_rank"] = None
                    merged[row_key] = existing

                existing["vector_score"] = max(
                    float(existing.get("vector_score") or 0.0),
                    float(row.get("vector_score") or 0.0),
                )
                existing["lexical_score"] = max(
                    float(existing.get("lexical_score") or 0.0),
                    float(row.get("lexical_score") or 0.0),
                )
                if source_name == "vector":
                    existing["vector_rank"] = source_rank
                else:
                    existing["lexical_rank"] = source_rank
                    has_lexical_hits = True

        reranked_rows = list(merged.values())
        for row in reranked_rows:
            row["score"] = self._hybrid_score(
                query=query,
                row=row,
                has_lexical_hits=has_lexical_hits,
            )

        reranked_rows.sort(
            key=lambda row: (
                float(row["score"]),
                float(row.get("vector_score") or 0.0),
                -(row.get("vector_rank") or self.MAX_HYBRID_CANDIDATES + 1),
            ),
            reverse=True,
        )
        return reranked_rows[:top_k]

    def _hybrid_score(
        self,
        *,
        query: str,
        row: dict[str, Any],
        has_lexical_hits: bool,
    ) -> float:
        vector_score = float(row.get("vector_score") or 0.0)
        lexical_score = float(row.get("lexical_score") or 0.0)
        if not has_lexical_hits:
            return vector_score

        lexical_component = min(lexical_score * 8.0, 1.0)
        phrase_component = self._phrase_overlap_score(query=query, row=row)
        combined = (
            (self._hybrid_vector_weight() * vector_score)
            + (self._hybrid_lexical_weight() * lexical_component)
            + (self._hybrid_phrase_weight() * phrase_component)
        )
        return min(round(combined, 12), 1.0)

    def _hybrid_vector_weight(self) -> float:
        return float(
            getattr(self, "hybrid_vector_weight", self.DEFAULT_HYBRID_VECTOR_WEIGHT)
        )

    def _hybrid_lexical_weight(self) -> float:
        return float(
            getattr(self, "hybrid_lexical_weight", self.DEFAULT_HYBRID_LEXICAL_WEIGHT)
        )

    def _hybrid_phrase_weight(self) -> float:
        return float(
            getattr(self, "hybrid_phrase_weight", self.DEFAULT_HYBRID_PHRASE_WEIGHT)
        )

    def _phrase_overlap_score(self, *, query: str, row: dict[str, Any]) -> float:
        searchable_text = " ".join(
            [
                str(row.get("file_name") or ""),
                json.dumps(row.get("child_json") or {}, ensure_ascii=False),
                json.dumps(row.get("parent_json") or {}, ensure_ascii=False),
            ]
        )
        query_tokens = meaningful_tokens(query)
        if not query_tokens:
            return 0.0

        text_tokens = set(meaningful_tokens(searchable_text))
        if not text_tokens:
            return 0.0

        matched_tokens = sum(1 for token in query_tokens if token in text_tokens)
        return matched_tokens / len(query_tokens)

    def _retrieved_chunk_from_row(
        self,
        *,
        row: dict[str, Any],
        rank: int,
    ) -> RetrievedChunk:
        child_chunk = ChildChunk.model_validate(self._loads_json(row["child_json"]))
        parent_chunk = ParentChunk.model_validate(self._loads_json(row["parent_json"]))
        return RetrievedChunk(
            rank=rank,
            score=float(row.get("score") or row.get("vector_score") or 0.0),
            child_chunk=child_chunk,
            parent_chunk=parent_chunk,
            metadata={
                "vector_record_id": row["child_id"],
                "file_name": row["file_name"],
                "file_type": row["file_type"],
                "vector_score": float(row.get("vector_score") or 0.0),
                "lexical_score": float(row.get("lexical_score") or 0.0),
                "vector_rank": row.get("vector_rank"),
                "lexical_rank": row.get("lexical_rank"),
                "database_url": self._redacted_database_url(),
            },
        )

    def _candidate_limit(self, top_k: int) -> int:
        return min(
            max(top_k * 8, self.MIN_HYBRID_CANDIDATES),
            self.MAX_HYBRID_CANDIDATES,
        )

    def _stats(self, connection: Any) -> PgVectorIndexStats:
        metadata = self._metadata(connection)
        embedding_dimensions = metadata.get("embedding_dimensions")
        return PgVectorIndexStats(
            document_count=self._count_rows(connection, "documents"),
            parent_chunk_count=self._count_rows(connection, "parent_chunks"),
            child_chunk_count=self._count_rows(connection, "child_chunks"),
            embedding_model=metadata.get("embedding_model"),
            embedding_dimensions=(
                int(embedding_dimensions) if embedding_dimensions is not None else None
            ),
        )

    def _document_summary_from_row(self, row: dict[str, Any]) -> IndexedDocumentSummary:
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

    def _document_chunk_summary_from_row(
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

    def _metadata(self, connection: Any) -> dict[str, str]:
        return {
            row["key"]: row["value"]
            for row in connection.execute("SELECT key, value FROM index_metadata")
        }

    def _count_rows(self, connection: Any, table_name: str) -> int:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return int(row["count"])

    def _vector_to_sql(self, vector: EmbeddingVector) -> str:
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

    def _duration_ms(self, start_time: float) -> float:
        return round((perf_counter() - start_time) * 1000, 3)

    def _redacted_database_url(self) -> str:
        if "@" not in self.database_url:
            return self.database_url

        scheme_and_credentials, host = self.database_url.split("@", 1)
        scheme = scheme_and_credentials.split("://", 1)[0]
        return f"{scheme}://***@{host}"


def meaningful_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "be",
        "can",
        "do",
        "does",
        "for",
        "how",
        "is",
        "it",
        "of",
        "or",
        "should",
        "the",
        "to",
        "what",
        "when",
        "which",
        "who",
    }
    return [singularize_token(token) for token in tokens if token not in stop_words]


def singularize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def configured_float(env_name: str, default: float) -> float:
    raw_value = os.getenv(env_name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise RetrievalError(
            "Float environment setting is invalid",
            code="INVALID_FLOAT_ENV",
            details={"env_name": env_name, "value": raw_value},
        ) from exc
