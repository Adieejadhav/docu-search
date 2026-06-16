"""
File: backend/app/embeddings/local_sentence_transformer.py
Purpose: Provides local open-source embedding support through sentence-transformers.
"""

from __future__ import annotations

import os
from typing import Any

from app.core.exceptions import EmbeddingError
from app.core.env import load_environment

from .base import EmbeddingProvider, EmbeddingVector, validate_embedding_vector


class LocalSentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """
    Production embedding provider backed by a local sentence-transformers model.
    """

    DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
    DEFAULT_DIMENSIONS = 384
    DEFAULT_BATCH_SIZE = 64

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        device: str | None = None,
        model_client: Any | None = None,
    ) -> None:
        load_environment()
        if dimensions < 1:
            raise EmbeddingError(
                "Local embedding dimensions must be greater than zero",
                code="INVALID_LOCAL_EMBEDDING_DIMENSIONS",
                details={"dimensions": dimensions},
            )

        if batch_size < 1:
            raise EmbeddingError(
                "Local embedding batch_size must be greater than zero",
                code="INVALID_LOCAL_EMBEDDING_BATCH_SIZE",
                details={"batch_size": batch_size},
            )

        self._model_name = model
        self._dimensions = dimensions
        self._batch_size = batch_size
        self._device = device or os.getenv("LOCAL_EMBEDDING_DEVICE") or None
        self._model_client = model_client

    @property
    def name(self) -> str:
        return f"local-sentence-transformers-{self._model_name}-{self._dimensions}d"

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        if not texts:
            return []

        for index, text in enumerate(texts):
            if not text or not text.strip():
                raise EmbeddingError(
                    "Cannot embed empty text",
                    code="EMPTY_EMBEDDING_TEXT",
                    details={"text_index": index},
                )

        embeddings: list[EmbeddingVector] = []
        model_client = self._get_model_client()
        for batch in self._batches(texts):
            raw_vectors = model_client.encode(
                batch,
                batch_size=min(self._batch_size, len(batch)),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            vectors = self._to_python_vectors(raw_vectors)
            embeddings.extend(
                validate_embedding_vector(
                    vector,
                    expected_dimensions=self._dimensions,
                )
                for vector in vectors
            )

        return embeddings

    def _get_model_client(self) -> Any:
        if self._model_client is not None:
            return self._model_client

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise EmbeddingError(
                "The sentence-transformers package is required for local embeddings",
                code="SENTENCE_TRANSFORMERS_PACKAGE_MISSING",
            ) from exc

        kwargs: dict[str, Any] = {}
        if self._device:
            kwargs["device"] = self._device

        self._model_client = SentenceTransformer(self._model_name, **kwargs)
        return self._model_client

    def _batches(self, texts: list[str]) -> list[list[str]]:
        return [
            texts[index : index + self._batch_size]
            for index in range(0, len(texts), self._batch_size)
        ]

    def _to_python_vectors(self, raw_vectors: Any) -> list[EmbeddingVector]:
        if hasattr(raw_vectors, "tolist"):
            raw_vectors = raw_vectors.tolist()

        if isinstance(raw_vectors, list):
            return [
                vector.tolist() if hasattr(vector, "tolist") else list(vector)
                for vector in raw_vectors
            ]

        return [list(vector) for vector in raw_vectors]
