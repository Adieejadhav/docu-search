"""
File: backend/app/search/embeddings/hash_embedding.py
Purpose: Provides deterministic local embeddings for development and tests.
"""

from __future__ import annotations

from collections import Counter
from hashlib import blake2b
from math import sqrt
import re

from app.core.exceptions import EmbeddingError

from .base import EmbeddingProvider, EmbeddingVector


class HashEmbeddingProvider(EmbeddingProvider):
    """
    Dependency-free lexical embedding provider.

    This is designed for local pipeline validation. It hashes tokens and small
    character n-grams into a fixed-size vector, then L2-normalizes the result.
    A real semantic embedding model can be swapped in behind the same interface.
    """

    TOKEN_PATTERN = re.compile(r"[\w]+", re.UNICODE)

    def __init__(self, *, dimensions: int = 384) -> None:
        if dimensions < 16:
            raise EmbeddingError(
                "Hash embedding dimensions must be at least 16",
                code="INVALID_HASH_EMBEDDING_DIMENSIONS",
                details={"dimensions": dimensions},
            )
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return f"hash-embedding-{self._dimensions}d-v1"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[EmbeddingVector]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> EmbeddingVector:
        if not text or not text.strip():
            raise EmbeddingError(
                "Cannot embed empty text",
                code="EMPTY_EMBEDDING_TEXT",
            )

        vector = [0.0] * self._dimensions
        for feature, weight in self._weighted_features(text).items():
            index, sign = self._feature_bucket(feature)
            vector[index] += sign * weight

        norm = sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector

        return [value / norm for value in vector]

    def _weighted_features(self, text: str) -> Counter[str]:
        tokens = self._tokens(text)
        features: Counter[str] = Counter()

        for token in tokens:
            features[f"tok:{token}"] += 1.0
            for gram in self._character_ngrams(token):
                features[f"ng:{gram}"] += 0.25

        for left, right in zip(tokens, tokens[1:]):
            features[f"bi:{left}_{right}"] += 0.5

        return features

    def _tokens(self, text: str) -> list[str]:
        return [
            token.casefold()
            for token in self.TOKEN_PATTERN.findall(text)
            if token.strip()
        ]

    def _character_ngrams(self, token: str) -> list[str]:
        if len(token) < 4:
            return []

        padded = f"^{token}$"
        return [padded[index : index + 3] for index in range(len(padded) - 2)]

    def _feature_bucket(self, feature: str) -> tuple[int, float]:
        digest = blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % self._dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        return bucket, sign
