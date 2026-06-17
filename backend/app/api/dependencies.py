"""
File: backend/app/api/dependencies.py
Purpose: Provides API dependency factories for indexing, retrieval, and RAG.
"""

from __future__ import annotations

from functools import lru_cache
import os

from app.core.env import load_environment
from app.core.exceptions import RetrievalError
from app.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.llm import OllamaChatClient
from app.rag import RagAnswerer


def get_database_url() -> str:
    load_environment()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RetrievalError(
            "DATABASE_URL is required",
            code="DATABASE_URL_MISSING",
        )
    return database_url


@lru_cache(maxsize=1)
def get_embedding_provider() -> LocalSentenceTransformerEmbeddingProvider:
    load_environment()
    return LocalSentenceTransformerEmbeddingProvider(
        model=os.getenv(
            "LOCAL_EMBEDDING_MODEL",
            LocalSentenceTransformerEmbeddingProvider.DEFAULT_MODEL,
        ),
        dimensions=int(
            os.getenv(
                "LOCAL_EMBEDDING_DIMENSIONS",
                str(LocalSentenceTransformerEmbeddingProvider.DEFAULT_DIMENSIONS),
            )
        ),
        batch_size=int(
            os.getenv(
                "LOCAL_EMBEDDING_BATCH_SIZE",
                str(LocalSentenceTransformerEmbeddingProvider.DEFAULT_BATCH_SIZE),
            )
        ),
        device=os.getenv("LOCAL_EMBEDDING_DEVICE"),
    )


def get_chunk_index() -> PgVectorChunkIndex:
    return PgVectorChunkIndex(
        database_url=get_database_url(),
        embedding_provider=get_embedding_provider(),
    )


@lru_cache(maxsize=1)
def get_llm_client() -> OllamaChatClient:
    load_environment()
    return OllamaChatClient(
        model=os.getenv("OLLAMA_MODEL", OllamaChatClient.DEFAULT_MODEL),
        host=os.getenv("OLLAMA_HOST", OllamaChatClient.DEFAULT_HOST),
        temperature=float(os.getenv("OLLAMA_TEMPERATURE", "0")),
    )


@lru_cache(maxsize=1)
def get_rag_answerer() -> RagAnswerer:
    return RagAnswerer(llm_client=get_llm_client())
