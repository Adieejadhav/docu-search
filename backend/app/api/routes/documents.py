from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.api.dependencies import get_chunk_index, get_ingestion_job_service
from app.core.exceptions import RetrievalError
from app.indexing import PgVectorChunkIndex
from app.ingestion.jobs import IngestionJobService
from app.schemas import (
    DocumentChunkListResponse,
    DocumentChunkSummary,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentSummary,
    IngestionJobCreateResponse,
    IngestionJobResponse,
)

router = APIRouter()
admin_router = APIRouter()


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> DocumentListResponse:
    stats = index.stats()
    documents = index.list_documents(limit=limit, offset=offset)
    return DocumentListResponse(
        total=stats.document_count,
        limit=limit,
        offset=offset,
        documents=[
            DocumentSummary.model_validate(document)
            for document in documents
        ],
    )


@admin_router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
def list_document_chunks(
    document_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> DocumentChunkListResponse:
    document = index.get_document(document_id)
    if document is None:
        raise RetrievalError(
            "Document was not found",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": document_id},
        )

    total, chunks = index.list_document_chunks(
        document_id,
        limit=limit,
        offset=offset,
    )
    return DocumentChunkListResponse(
        document=DocumentSummary.model_validate(document),
        total=total,
        limit=limit,
        offset=offset,
        chunks=[DocumentChunkSummary.model_validate(chunk) for chunk in chunks],
    )


@admin_router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: str,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> DocumentDeleteResponse:
    deleted = index.delete_document(document_id)
    if not deleted:
        raise RetrievalError(
            "Document was not found",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": document_id},
        )

    return DocumentDeleteResponse(status="deleted", document_id=document_id)


@admin_router.post("/{document_id}/reindex", response_model=IngestionJobCreateResponse)
def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobCreateResponse:
    document = index.get_document(document_id)
    if document is None:
        raise RetrievalError(
            "Document was not found",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": document_id},
        )
    if not document.source_path:
        raise RetrievalError(
            "Document cannot be re-indexed because source_path is missing",
            code="DOCUMENT_SOURCE_PATH_MISSING",
            details={"document_id": document_id},
        )

    job = service.create_job(
        source_paths=[Path(document.source_path)],
        source_kind="reindex",
        options={
            "recursive": False,
            "clear_index": False,
            "replace": True,
            "continue_on_error": False,
            "document_id": document_id,
        },
    )
    if ingestion_run_mode() == "background":
        background_tasks.add_task(service.run_job, job.id)
    return IngestionJobCreateResponse(
        job=IngestionJobResponse.model_validate(job),
    )


def ingestion_run_mode() -> str:
    mode = os.getenv("INGESTION_RUN_MODE", "background").strip().lower()
    if mode not in {"background", "worker"}:
        raise RetrievalError(
            "INGESTION_RUN_MODE must be 'background' or 'worker'",
            code="INVALID_INGESTION_RUN_MODE",
            details={"INGESTION_RUN_MODE": mode},
        )
    return mode
