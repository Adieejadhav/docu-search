"""
File: backend/app/api/dependencies.py
Purpose: Provides API dependency factories for indexing, retrieval, and RAG.
"""

from __future__ import annotations

from functools import lru_cache
import os

from fastapi import Header

from app.core.env import load_environment
from app.core.exceptions import AuthenticationError, RetrievalError
from app.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.ingestion.jobs import IngestionJobService
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


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """
    Protects admin routes when ADMIN_API_TOKEN is configured.

    Local development remains open by default. Production deployments should set
    ADMIN_API_TOKEN and pass it as X-Admin-Token from the frontend or API client.
    """

    load_environment()
    expected_token = os.getenv("ADMIN_API_TOKEN")
    if not expected_token:
        return

    if x_admin_token != expected_token:
        raise AuthenticationError(
            "A valid admin token is required",
            code="ADMIN_AUTH_REQUIRED",
        )


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


def get_ingestion_job_service() -> IngestionJobService:
    from app.ingestion import IngestionOrchestrator

    return IngestionJobService(
        orchestrator=IngestionOrchestrator(index=get_chunk_index()),
    )


def get_rag_trace_store():
    from app.rag.traces import RagTraceStore

    return RagTraceStore(database_url=get_database_url())


def get_chat_store():
    from app.chat.store import ChatStore

    return ChatStore(database_url=get_database_url())


def get_evaluation_history_store():
    from app.evaluation.history import EvaluationHistoryStore

    return EvaluationHistoryStore(database_url=get_database_url())


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
