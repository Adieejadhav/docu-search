"""
File: backend/app/search/embeddings/pipeline.py
Purpose: Convenience entry points for embedding chunk text.
"""

from __future__ import annotations

from app.ingestion.chunking import ChildChunk

from .base import EmbeddingProvider, EmbeddingVector
from .hash_embedding import HashEmbeddingProvider


DEFAULT_EMBEDDING_PROVIDER = HashEmbeddingProvider()


def embed_child_chunks(
    child_chunks: list[ChildChunk],
    *,
    provider: EmbeddingProvider | None = None,
) -> dict[str, EmbeddingVector]:
    embedding_provider = provider or DEFAULT_EMBEDDING_PROVIDER
    vectors = embedding_provider.embed_texts([chunk.text for chunk in child_chunks])
    return {
        child_chunk.id: vector
        for child_chunk, vector in zip(child_chunks, vectors, strict=True)
    }
