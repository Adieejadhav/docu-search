"""
File: backend/app/indexing/pgvector_index.py
Purpose: Provides production PostgreSQL + pgvector indexing and retrieval.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from time import perf_counter
from typing import Any

from app.core.exceptions import RetrievalError
from app.core.env import load_environment
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


class PgVectorChunkIndex:
    """
    Production chunk/vector index backed by PostgreSQL and pgvector.
    """

    SCHEMA_VERSION = 1

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

    def initialize(self) -> None:
        with self._connect() as connection:
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
            rows = self._search_rows(
                connection=connection,
                query_vector_text=query_vector_text,
                top_k=top_k,
                metadata_filters=metadata_filters,
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
            },
        )

    def stats(self, *, connection: Any | None = None) -> PgVectorIndexStats:
        if connection is not None:
            return self._stats(connection)

        self.initialize()
        with self._connect() as owned_connection:
            return self._stats(owned_connection)

    def _connect(self) -> Any:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RetrievalError(
                "The psycopg[binary] package is required for PostgreSQL indexing",
                code="PSYCOPG_PACKAGE_MISSING",
            ) from exc

        return psycopg.connect(self.database_url, row_factory=dict_row)

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

    def _search_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
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
                    1 - (ce.embedding <=> %s::vector) AS score
                FROM child_chunks cc
                JOIN child_embeddings ce ON ce.child_chunk_id = cc.id
                JOIN parent_chunks pc ON pc.id = cc.parent_chunk_id
                JOIN documents d ON d.id = cc.document_id
                {where_clause}
                ORDER BY ce.embedding <=> %s::vector
                LIMIT %s
                """,
                [query_vector_text, *filter_params, query_vector_text, top_k],
            )
        )

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
            score=float(row["score"]),
            child_chunk=child_chunk,
            parent_chunk=parent_chunk,
            metadata={
                "vector_record_id": row["child_id"],
                "file_name": row["file_name"],
                "file_type": row["file_type"],
                "database_url": self._redacted_database_url(),
            },
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
