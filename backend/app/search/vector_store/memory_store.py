"""
File: backend/app/search/vector_store/memory_store.py
Purpose: Provides an in-memory vector store for local retrieval and tests.
"""

from __future__ import annotations

from math import sqrt
from typing import Any

from app.core.exceptions import RetrievalError
from app.search.embeddings import EmbeddingVector, validate_embedding_vector

from .base import VectorRecord, VectorSearchResult, VectorStore


class InMemoryVectorStore(VectorStore):
    """
    Simple exact-search vector store.

    This keeps the retrieval contract testable before adding pgvector or another
    production vector backend.
    """

    def __init__(self, *, dimensions: int | None = None) -> None:
        self._dimensions = dimensions
        self._records: dict[str, VectorRecord] = {}

    @property
    def dimensions(self) -> int | None:
        return self._dimensions

    def upsert(self, records: list[VectorRecord]) -> None:
        for record in records:
            self._validate_record(record)
            self._records[record.id] = VectorRecord(
                id=record.id,
                vector=list(record.vector),
                text=record.text,
                metadata=dict(record.metadata),
            )

    def search(
        self,
        query_vector: EmbeddingVector,
        *,
        top_k: int,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        if top_k < 1:
            raise RetrievalError(
                "top_k must be greater than zero",
                code="INVALID_TOP_K",
                details={"top_k": top_k},
            )

        query = validate_embedding_vector(
            query_vector,
            expected_dimensions=self._dimensions,
        )
        scored_records = [
            (self._cosine_similarity(query, record.vector), record)
            for record in self._records.values()
            if self._matches_filters(record, metadata_filters)
        ]
        scored_records.sort(key=lambda item: (-item[0], item[1].id))

        return [
            VectorSearchResult(record=record, score=score, rank=rank)
            for rank, (score, record) in enumerate(scored_records[:top_k], start=1)
        ]

    def get(self, record_id: str) -> VectorRecord | None:
        return self._records.get(record_id)

    def clear(self) -> None:
        self._records.clear()

    def count(self) -> int:
        return len(self._records)

    def _validate_record(self, record: VectorRecord) -> None:
        if not record.id.strip():
            raise RetrievalError(
                "Vector record id cannot be empty",
                code="EMPTY_VECTOR_RECORD_ID",
            )

        if not record.text.strip():
            raise RetrievalError(
                "Vector record text cannot be empty",
                code="EMPTY_VECTOR_RECORD_TEXT",
                details={"record_id": record.id},
            )

        vector = validate_embedding_vector(
            record.vector,
            expected_dimensions=self._dimensions,
        )
        if self._dimensions is None:
            self._dimensions = len(vector)

    def _matches_filters(
        self,
        record: VectorRecord,
        metadata_filters: dict[str, Any] | None,
    ) -> bool:
        if not metadata_filters:
            return True

        return all(
            record.metadata.get(key) == value
            for key, value in metadata_filters.items()
        )

    def _cosine_similarity(
        self,
        left: EmbeddingVector,
        right: EmbeddingVector,
    ) -> float:
        left_norm = sqrt(sum(value * value for value in left))
        right_norm = sqrt(sum(value * value for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0

        return sum(a * b for a, b in zip(left, right, strict=True)) / (
            left_norm * right_norm
        )
