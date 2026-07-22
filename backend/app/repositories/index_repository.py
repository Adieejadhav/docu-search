"""
File: backend/app/repositories/index_repository.py
Purpose: Owns pgvector index schema compatibility, metadata, stats, and clearing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.integrations.database import DatabasePool, connect_postgres
from app.integrations.embeddings import EmbeddingProvider, EmbeddingVector


@dataclass(frozen=True)
class PgVectorIndexStats:
    document_count: int
    parent_chunk_count: int
    child_chunk_count: int
    embedding_model: str | None
    embedding_dimensions: int | None


class IndexRepository:
    """
    Repository for index schema compatibility, metadata, stats, and clear operations.

    Historical migrations remain under app.integrations.database.migrations. The
    inline CREATE IF NOT EXISTS statements here preserve the existing runtime
    compatibility behavior of PgVectorChunkIndex for deployments that start
    against an empty database.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        database_url: str | None = None,
        embedding_provider: EmbeddingProvider,
        database_pool: DatabasePool | None = None,
    ) -> None:
        self.database_pool = database_pool
        self.database_url = database_url or getattr(database_pool, "database_url", None)
        self.database_url = self.database_url or get_settings().database.url
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for PostgreSQL pgvector indexing",
                code="DATABASE_URL_MISSING",
            )
        self.embedding_provider = embedding_provider

    def initialize(self) -> None:
        with self.connect() as connection:
            self.lock_schema_initialization(connection)
            self.create_schema(connection)
            self.validate_or_set_index_metadata(connection)

    def connect(self) -> Any:
        if self.database_pool is not None:
            return self.database_pool.connection()
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for PostgreSQL indexing"
            ),
        )

    def clear(self) -> None:
        self.initialize()
        with self.connect() as connection:
            self.clear_with_connection(connection)

    def clear_with_connection(self, connection: Any) -> None:
        for table_name in (
            "child_embeddings",
            "child_chunks",
            "parent_chunks",
            "documents",
        ):
            connection.execute(f"DELETE FROM {table_name}")

    def stats(self, *, connection: Any | None = None) -> PgVectorIndexStats:
        if connection is not None:
            return self.stats_with_connection(connection)

        self.initialize()
        with self.connect() as owned_connection:
            return self.stats_with_connection(owned_connection)

    def stats_with_connection(self, connection: Any) -> PgVectorIndexStats:
        metadata = self.metadata(connection)
        embedding_dimensions = metadata.get("embedding_dimensions")
        return PgVectorIndexStats(
            document_count=self.count_rows(connection, "documents"),
            parent_chunk_count=self.count_rows(connection, "parent_chunks"),
            child_chunk_count=self.count_rows(connection, "child_chunks"),
            embedding_model=metadata.get("embedding_model"),
            embedding_dimensions=(
                int(embedding_dimensions) if embedding_dimensions is not None else None
            ),
        )

    def vector_to_sql(self, vector: EmbeddingVector) -> str:
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

    def lock_schema_initialization(self, connection: Any) -> None:
        connection.execute("SELECT pg_advisory_xact_lock(420240519826)")

    def create_schema(self, connection: Any) -> None:
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

    def validate_or_set_index_metadata(self, connection: Any) -> None:
        metadata = self.metadata(connection)
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

    def metadata(self, connection: Any) -> dict[str, str]:
        return {
            row["key"]: row["value"]
            for row in connection.execute("SELECT key, value FROM index_metadata")
        }

    def count_rows(self, connection: Any, table_name: str) -> int:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return int(row["count"])
