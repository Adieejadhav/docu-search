"""
File: backend/app/search/vector_store/base.py
Purpose: Defines vector store records and the search store contract.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.search.embeddings import EmbeddingVector


@dataclass(frozen=True)
class VectorRecord:
    id: str
    vector: EmbeddingVector
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VectorSearchResult:
    record: VectorRecord
    score: float
    rank: int


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, records: list[VectorRecord]) -> None:
        """Insert or replace records."""

    @abstractmethod
    def search(
        self,
        query_vector: EmbeddingVector,
        *,
        top_k: int,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Return nearest records for the query vector."""

    @abstractmethod
    def get(self, record_id: str) -> VectorRecord | None:
        """Return one record by id."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all records."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored vectors."""
