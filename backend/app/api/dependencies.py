"""
File: backend/app/api/dependencies.py
Purpose: Provides API dependency factories for indexing, retrieval, and RAG.
"""

from __future__ import annotations

from fastapi import Depends

from app.bootstrap import get_application_container
from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.integrations.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.repositories import PgVectorChunkIndex
from app.ingestion.jobs import IngestionJobService
from app.ingestion.pipeline_testing import PipelineNodeTester
from app.integrations.llm import OllamaChatClient
from app.rag import RagAnswerer
from app.repositories import DocumentRepository
from app.services import (
    AdminService,
    DocumentService,
    IngestionService,
    SearchService,
    TraceService,
)


def get_database_url() -> str:
    database_url = get_settings().database.url
    if not database_url:
        raise RetrievalError(
            "DATABASE_URL is required",
            code="DATABASE_URL_MISSING",
        )
    return database_url


def get_embedding_provider() -> LocalSentenceTransformerEmbeddingProvider:
    return get_application_container().embedding_provider


def get_chunk_index() -> PgVectorChunkIndex:
    return get_application_container().chunk_index


def get_document_repository(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> DocumentRepository:
    return DocumentRepository(index=index)


def get_document_service(
    repository: DocumentRepository = Depends(get_document_repository),
) -> DocumentService:
    return DocumentService(repository=repository)


def get_admin_service(
    repository: DocumentRepository = Depends(get_document_repository),
) -> AdminService:
    return AdminService(document_repository=repository)


def get_ingestion_job_service() -> IngestionJobService:
    return get_application_container().ingestion_job_service


def get_ingestion_service(
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionService:
    return IngestionService(job_service=job_service)


def get_pipeline_node_tester() -> PipelineNodeTester:
    return get_application_container().pipeline_node_tester


def get_rag_trace_store():
    return get_application_container().rag_trace_store


def get_trace_service(store=Depends(get_rag_trace_store)) -> TraceService:
    return TraceService(store=store)


def get_chat_store():
    return get_application_container().chat_store


def get_llm_client() -> OllamaChatClient:
    return get_application_container().llm_client


def get_rag_answerer() -> RagAnswerer:
    return get_application_container().rag_answerer


def get_search_service(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    trace_store=Depends(get_rag_trace_store),
) -> SearchService:
    return SearchService(
        index=index,
        answerer=answerer,
        trace_store=trace_store,
    )


def get_chat_service(
    store=Depends(get_chat_store),
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    trace_store=Depends(get_rag_trace_store),
):
    from app.services.chat_service import ChatService

    return ChatService(
        store=store,
        index=index,
        answerer=answerer,
        trace_store=trace_store,
    )
