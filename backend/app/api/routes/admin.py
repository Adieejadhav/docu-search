from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from app.admin import AdminOverviewService
from app.api.dependencies import (
    get_chunk_index,
    get_database_url,
    get_embedding_provider,
    get_llm_client,
)
from app.api.middleware import metrics_snapshot
from app.core.exceptions import RetrievalError
from app.embeddings import EmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.llm import OllamaChatClient
from app.schemas import AdminClearIndexRequest, AdminClearIndexResponse, AdminOverviewResponse

router = APIRouter()


@router.post("/index/clear", response_model=AdminClearIndexResponse)
def clear_index(
    request: AdminClearIndexRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> AdminClearIndexResponse:
    if not request.confirm:
        raise RetrievalError(
            "Index clear requires confirm=true",
            code="INDEX_CLEAR_NOT_CONFIRMED",
        )

    index.clear()
    stats = index.stats()
    return AdminClearIndexResponse(
        status="cleared",
        document_count=stats.document_count,
        parent_chunk_count=stats.parent_chunk_count,
        child_chunk_count=stats.child_chunk_count,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    database_url: str = Depends(get_database_url),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_client: OllamaChatClient = Depends(get_llm_client),
) -> AdminOverviewResponse:
    """
    Returns database-backed data for the admin overview dashboard.
    """

    return AdminOverviewService(
        database_url=database_url,
        index=index,
        embedding_provider=embedding_provider,
        llm_client=llm_client,
    ).build()


@router.get("/metrics")
def get_api_metrics() -> dict:
    return metrics_snapshot()


@router.get("/auth/status")
def get_admin_auth_status() -> dict:
    return {
        "admin_token_required": bool(os.getenv("ADMIN_API_TOKEN")),
    }
