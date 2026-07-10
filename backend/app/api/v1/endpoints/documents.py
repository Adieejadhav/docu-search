from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_document_service, get_ingestion_job_service
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
from app.services import DocumentService

router = APIRouter()
admin_router = APIRouter()


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    result = service.list_documents(limit=limit, offset=offset)
    return DocumentListResponse(
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        documents=[
            DocumentSummary.model_validate(document)
            for document in result.documents
        ],
    )


@router.get("/{document_id}/source")
def open_document_source(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> FileResponse:
    source_file = service.get_document_source(document_id)
    return FileResponse(
        source_file.path,
        media_type=source_file.media_type,
        filename=source_file.file_name,
        content_disposition_type="inline",
    )


@admin_router.get("/{document_id}/chunks", response_model=DocumentChunkListResponse)
def list_document_chunks(
    document_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: DocumentService = Depends(get_document_service),
) -> DocumentChunkListResponse:
    result = service.list_document_chunks(
        document_id,
        limit=limit,
        offset=offset,
    )
    return DocumentChunkListResponse(
        document=DocumentSummary.model_validate(result.document),
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        chunks=[DocumentChunkSummary.model_validate(chunk) for chunk in result.chunks],
    )


@admin_router.delete("/{document_id}", response_model=DocumentDeleteResponse)
def delete_document(
    document_id: str,
    service: DocumentService = Depends(get_document_service),
) -> DocumentDeleteResponse:
    deleted_document_id = service.delete_document(document_id)
    return DocumentDeleteResponse(status="deleted", document_id=deleted_document_id)


@admin_router.post("/{document_id}/reindex", response_model=IngestionJobCreateResponse)
def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    document_service: DocumentService = Depends(get_document_service),
    service: IngestionJobService = Depends(get_ingestion_job_service),
) -> IngestionJobCreateResponse:
    plan = document_service.create_reindex_job(
        document_id,
        ingestion_jobs=service,
    )
    if plan.run_in_background:
        background_tasks.add_task(service.run_job, plan.job.id)
    return IngestionJobCreateResponse(
        job=IngestionJobResponse.model_validate(plan.job),
    )
