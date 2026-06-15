"""
File: backend/app/search/retrieval/retriever.py
Purpose: Implements child-vector retrieval with parent chunk expansion.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.core.exceptions import RetrievalError
from app.ingestion.chunking import ChildChunk, ChunkedDocument, ParentChunk
from app.search.embeddings import EmbeddingProvider, HashEmbeddingProvider
from app.search.vector_store import InMemoryVectorStore, VectorRecord, VectorStore

from .retrieval_schema import RetrievedChunk, RetrievalResult


class ParentChildRetriever:
    """
    Indexes child chunks and returns parent-expanded retrieval results.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()
        self.vector_store = vector_store or InMemoryVectorStore(
            dimensions=self.embedding_provider.dimensions
        )
        self._parents_by_id: dict[str, ParentChunk] = {}
        self._children_by_id: dict[str, ChildChunk] = {}
        self._documents_by_id: dict[str, ChunkedDocument] = {}

    def clear(self) -> None:
        self.vector_store.clear()
        self._parents_by_id.clear()
        self._children_by_id.clear()
        self._documents_by_id.clear()

    def index_document(self, document: ChunkedDocument) -> int:
        return self.index_documents([document])

    def index_documents(self, documents: Iterable[ChunkedDocument]) -> int:
        records: list[VectorRecord] = []

        for document in documents:
            self._documents_by_id[document.document_id] = document

            for parent_chunk in document.parent_chunks:
                self._parents_by_id[parent_chunk.id] = parent_chunk

            vectors = self.embedding_provider.embed_texts(
                [child_chunk.text for child_chunk in document.child_chunks]
            )
            for child_chunk, vector in zip(
                document.child_chunks,
                vectors,
                strict=True,
            ):
                self._children_by_id[child_chunk.id] = child_chunk
                records.append(
                    VectorRecord(
                        id=child_chunk.id,
                        vector=vector,
                        text=child_chunk.text,
                        metadata={
                            "document_id": child_chunk.document_id,
                            "parent_chunk_id": child_chunk.parent_chunk_id,
                            "child_index": child_chunk.child_index,
                            "file_name": document.file_name,
                            "file_type": document.file_type,
                        },
                    )
                )

        self.vector_store.upsert(records)
        return len(records)

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

        query_vector = self.embedding_provider.embed_text(query)
        search_results = self.vector_store.search(
            query_vector,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )

        results: list[RetrievedChunk] = []
        for search_result in search_results:
            child_chunk = self._children_by_id.get(search_result.record.id)
            if child_chunk is None:
                raise RetrievalError(
                    "Vector store returned an unknown child chunk id",
                    code="UNKNOWN_CHILD_CHUNK",
                    details={"child_chunk_id": search_result.record.id},
                )

            parent_chunk = self._parents_by_id.get(child_chunk.parent_chunk_id)
            if parent_chunk is None:
                raise RetrievalError(
                    "Child chunk references an unknown parent chunk",
                    code="UNKNOWN_PARENT_CHUNK",
                    details={
                        "child_chunk_id": child_chunk.id,
                        "parent_chunk_id": child_chunk.parent_chunk_id,
                    },
                )

            results.append(
                RetrievedChunk(
                    rank=search_result.rank,
                    score=search_result.score,
                    child_chunk=child_chunk,
                    parent_chunk=parent_chunk,
                    metadata={
                        "vector_record_id": search_result.record.id,
                        "file_name": search_result.record.metadata.get("file_name"),
                        "file_type": search_result.record.metadata.get("file_type"),
                    },
                )
            )

        return RetrievalResult(
            query=query,
            embedding_model=self.embedding_provider.name,
            top_k=top_k,
            results=results,
            metadata={
                "indexed_document_count": len(self._documents_by_id),
                "indexed_child_chunk_count": len(self._children_by_id),
                "vector_store_count": self.vector_store.count(),
            },
        )
