"""
File: backend/app/repositories/search_repository.py
Purpose: Coordinates retrieval and preserves the PgVectorChunkIndex facade.
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.ingestion.chunking import ChildChunk, ChunkedDocument, ParentChunk
from app.integrations.database import DatabasePool
from app.integrations.embeddings import (
    EmbeddingProvider,
    EmbeddingVector,
    LocalSentenceTransformerEmbeddingProvider,
)
from app.integrations.search import (
    HybridSearchRanker,
    HybridSearchWeights,
    LexicalSearch,
    PgVectorSearch,
)
from app.rag.retrieval import RetrievedChunk, RetrievalResult
from app.repositories.chunk_repository import ChunkRepository, IndexedDocumentChunkSummary
from app.repositories.document_repository import DocumentRepository, IndexedDocumentSummary
from app.repositories.index_repository import IndexRepository, PgVectorIndexStats

IndexProgressCallback = Callable[[dict[str, Any]], None]


class SearchRepository:
    """Application-friendly retrieval coordination over search integrations."""

    def __init__(
        self,
        *,
        database_url: str,
        embedding_provider: EmbeddingProvider,
        index_repository: IndexRepository,
        hybrid_ranker: HybridSearchRanker,
        pgvector_search: PgVectorSearch,
        lexical_search: LexicalSearch,
        min_hybrid_candidates: int,
        max_hybrid_candidates: int,
    ) -> None:
        self.database_url = database_url
        self.embedding_provider = embedding_provider
        self.index_repository = index_repository
        self.hybrid_ranker = hybrid_ranker
        self.pgvector_search = pgvector_search
        self.lexical_search = lexical_search
        self.min_hybrid_candidates = min_hybrid_candidates
        self.max_hybrid_candidates = max_hybrid_candidates

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

        self.index_repository.initialize()
        query_vector = self.embedding_provider.embed_text(query)
        query_vector_text = self.index_repository.vector_to_sql(query_vector)

        with self.index_repository.connect() as connection:
            vector_rows = self.search_vector_rows(
                connection=connection,
                query_vector_text=query_vector_text,
                query=query,
                top_k=self.candidate_limit(top_k),
                metadata_filters=metadata_filters,
            )
            lexical_rows = self.search_lexical_rows(
                connection=connection,
                query_vector_text=query_vector_text,
                query=query,
                top_k=self.candidate_limit(top_k),
                metadata_filters=metadata_filters,
            )
            rows = self.merge_and_rerank_rows(
                query=query,
                vector_rows=vector_rows,
                lexical_rows=lexical_rows,
                top_k=top_k,
            )
            results = [
                self.retrieved_chunk_from_row(row=row, rank=rank)
                for rank, row in enumerate(rows, start=1)
            ]
            stats = self.index_repository.stats(connection=connection)

        return RetrievalResult(
            query=query,
            embedding_model=self.embedding_provider.name,
            top_k=top_k,
            results=results,
            metadata={
                "database_url": self.redacted_database_url(),
                "indexed_document_count": stats.document_count,
                "indexed_parent_chunk_count": stats.parent_chunk_count,
                "indexed_child_chunk_count": stats.child_chunk_count,
                "retrieval_mode": "hybrid_vector_full_text",
                "hybrid_weights": {
                    "vector": self.hybrid_ranker.weights.vector,
                    "lexical": self.hybrid_ranker.weights.lexical,
                    "phrase": self.hybrid_ranker.weights.phrase,
                },
            },
        )

    def search_vector_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return self.pgvector_search.search_rows(
            connection=connection,
            query_vector_text=query_vector_text,
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

    def search_lexical_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return self.lexical_search.search_rows(
            connection=connection,
            query_vector_text=query_vector_text,
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

    def merge_and_rerank_rows(
        self,
        *,
        query: str,
        vector_rows: list[dict[str, Any]],
        lexical_rows: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        return self.hybrid_ranker.merge_and_rerank_rows(
            query=query,
            vector_rows=vector_rows,
            lexical_rows=lexical_rows,
            top_k=top_k,
        )

    def retrieved_chunk_from_row(
        self,
        *,
        row: dict[str, Any],
        rank: int,
    ) -> RetrievedChunk:
        child_chunk = ChildChunk.model_validate(row["child_json"])
        parent_chunk = ParentChunk.model_validate(row["parent_json"])
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
                "database_url": self.redacted_database_url(),
            },
        )

    def candidate_limit(self, top_k: int) -> int:
        return min(
            max(top_k * 8, self.min_hybrid_candidates),
            self.max_hybrid_candidates,
        )

    def redacted_database_url(self) -> str:
        if "@" not in self.database_url:
            return self.database_url

        scheme_and_credentials, host = self.database_url.split("@", 1)
        scheme = scheme_and_credentials.split("://", 1)[0]
        return f"{scheme}://***@{host}"


class PgVectorChunkIndex:
    """
    Compatibility facade for the PostgreSQL/pgvector chunk index.

    Existing services, CLI scripts, and tests keep using this class while
    focused repositories own the concrete persistence and retrieval details.
    """

    SCHEMA_VERSION = IndexRepository.SCHEMA_VERSION
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
        database_pool: DatabasePool | None = None,
    ) -> None:
        settings = get_settings()
        self.database_pool = database_pool
        self.database_url = database_url or getattr(database_pool, "database_url", None)
        self.database_url = self.database_url or settings.database.url
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for PostgreSQL pgvector indexing",
                code="DATABASE_URL_MISSING",
            )

        self.embedding_provider = (
            embedding_provider or LocalSentenceTransformerEmbeddingProvider()
        )
        self.hybrid_vector_weight = settings.search.hybrid_vector_weight
        self.hybrid_lexical_weight = settings.search.hybrid_lexical_weight
        self.hybrid_phrase_weight = settings.search.hybrid_phrase_weight
        self.hybrid_ranker = HybridSearchRanker(
            weights=HybridSearchWeights(
                vector=self.hybrid_vector_weight,
                lexical=self.hybrid_lexical_weight,
                phrase=self.hybrid_phrase_weight,
            ),
            max_hybrid_candidates=self.MAX_HYBRID_CANDIDATES,
        )
        self.pgvector_search = PgVectorSearch()
        self.lexical_search = LexicalSearch()
        self.index_repository = IndexRepository(
            database_url=self.database_url,
            embedding_provider=self.embedding_provider,
            database_pool=database_pool,
        )
        self.document_repository = DocumentRepository(
            database_url=self.database_url,
            index_repository=self.index_repository,
        )
        self.chunk_repository = ChunkRepository(
            database_url=self.database_url,
            embedding_provider=self.embedding_provider,
            index_repository=self.index_repository,
        )
        self.search_repository = SearchRepository(
            database_url=self.database_url,
            embedding_provider=self.embedding_provider,
            index_repository=self.index_repository,
            hybrid_ranker=self.hybrid_ranker,
            pgvector_search=self.pgvector_search,
            lexical_search=self.lexical_search,
            min_hybrid_candidates=self.MIN_HYBRID_CANDIDATES,
            max_hybrid_candidates=self.MAX_HYBRID_CANDIDATES,
        )

    def initialize(self) -> None:
        self.index_repository.initialize()

    def clear(self) -> None:
        self.index_repository.clear()

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
        return self.search_repository.retrieve(
            query,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

    def stats(self, *, connection: Any | None = None) -> PgVectorIndexStats:
        return self.index_repository.stats(connection=connection)

    def list_documents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[IndexedDocumentSummary]:
        return self.document_repository.list_documents(limit=limit, offset=offset)

    def get_document(self, document_id: str) -> IndexedDocumentSummary | None:
        return self.document_repository.get_document(document_id)

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[int, list[IndexedDocumentChunkSummary]]:
        return self.chunk_repository.list_document_chunks(
            document_id,
            limit=limit,
            offset=offset,
        )

    def delete_document(self, document_id: str) -> bool:
        self.initialize()
        with self._connect() as connection:
            return self.document_repository.delete_document(
                document_id,
                connection=connection,
            )

    def _connect(self) -> Any:
        return self.index_repository.connect()

    def _lock_schema_initialization(self, connection: Any) -> None:
        self.index_repository.lock_schema_initialization(connection)

    def _create_schema(self, connection: Any) -> None:
        self.index_repository.create_schema(connection)

    def _validate_or_set_index_metadata(self, connection: Any) -> None:
        self.index_repository.validate_or_set_index_metadata(connection)

    def _delete_document(self, connection: Any, document_id: str) -> None:
        self.chunk_repository.delete_chunks_for_document(
            connection=connection,
            document_id=document_id,
        )
        self.document_repository.delete_document_with_connection(
            connection=connection,
            document_id=document_id,
        )

    def _insert_document(self, connection: Any, document: ChunkedDocument) -> None:
        self.document_repository.create_or_replace_document(
            connection=connection,
            document=document,
        )

    def _insert_parent_chunks(self, connection: Any, document: ChunkedDocument) -> None:
        self.chunk_repository.save_parent_chunks(
            connection=connection,
            document=document,
        )

    def _insert_child_chunks(self, connection: Any, document: ChunkedDocument) -> int:
        return self.chunk_repository.save_child_chunks(
            connection=connection,
            document=document,
        )

    def _search_vector_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return self.search_repository.search_vector_rows(
            connection=connection,
            query_vector_text=query_vector_text,
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters,
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
        return self.search_repository.search_lexical_rows(
            connection=connection,
            query_vector_text=query_vector_text,
            query=query,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

    def _merge_and_rerank_rows(
        self,
        *,
        query: str,
        vector_rows: list[dict[str, Any]],
        lexical_rows: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        return self.search_repository.merge_and_rerank_rows(
            query=query,
            vector_rows=vector_rows,
            lexical_rows=lexical_rows,
            top_k=top_k,
        )

    def _hybrid_score(
        self,
        *,
        query: str,
        row: dict[str, Any],
        has_lexical_hits: bool,
    ) -> float:
        return self.hybrid_ranker.hybrid_score(
            query=query,
            row=row,
            has_lexical_hits=has_lexical_hits,
        )

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
        return self.hybrid_ranker.phrase_overlap_score(query=query, row=row)

    def _retrieved_chunk_from_row(
        self,
        *,
        row: dict[str, Any],
        rank: int,
    ) -> RetrievedChunk:
        return self.search_repository.retrieved_chunk_from_row(row=row, rank=rank)

    def _candidate_limit(self, top_k: int) -> int:
        return self.search_repository.candidate_limit(top_k)

    def _stats(self, connection: Any) -> PgVectorIndexStats:
        return self.index_repository.stats_with_connection(connection)

    def _document_summary_from_row(self, row: dict[str, Any]) -> IndexedDocumentSummary:
        return self.document_repository.document_summary_from_row(row)

    def _document_chunk_summary_from_row(
        self,
        row: dict[str, Any],
    ) -> IndexedDocumentChunkSummary:
        return self.chunk_repository.document_chunk_summary_from_row(row)

    def _metadata(self, connection: Any) -> dict[str, str]:
        return self.index_repository.metadata(connection)

    def _count_rows(self, connection: Any, table_name: str) -> int:
        return self.index_repository.count_rows(connection, table_name)

    def _vector_to_sql(self, vector: EmbeddingVector) -> str:
        return self.index_repository.vector_to_sql(vector)

    def _duration_ms(self, start_time: float) -> float:
        return round((perf_counter() - start_time) * 1000, 3)

    def _redacted_database_url(self) -> str:
        return self.search_repository.redacted_database_url()
