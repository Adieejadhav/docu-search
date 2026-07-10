"""
File: backend/app/embeddings/base.py
Purpose: Defines the embedding provider contract used by retrieval.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.exceptions import EmbeddingError

EmbeddingVector = list[float]


class EmbeddingProvider(ABC):
    """
    Provider interface for turning text into vectors.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider name for metadata and debugging."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Vector dimensionality returned by this provider."""

    def embed_text(self, text: str) -> EmbeddingVector:
        return self.embed_texts([text])[0]

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        """Embed a batch of texts."""


def validate_embedding_vector(
    vector: EmbeddingVector,
    *,
    expected_dimensions: int | None = None,
) -> EmbeddingVector:
    if not vector:
        raise EmbeddingError(
            "Embedding vector cannot be empty",
            code="EMPTY_EMBEDDING_VECTOR",
        )

    if expected_dimensions is not None and len(vector) != expected_dimensions:
        raise EmbeddingError(
            "Embedding vector has unexpected dimensions",
            code="INVALID_EMBEDDING_DIMENSIONS",
            details={
                "expected_dimensions": expected_dimensions,
                "actual_dimensions": len(vector),
            },
        )

    if any(not isinstance(value, int | float) for value in vector):
        raise EmbeddingError(
            "Embedding vector values must be numeric",
            code="INVALID_EMBEDDING_VALUE",
        )

    return [float(value) for value in vector]
