from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_chunk_index
from app.indexing import PgVectorChunkIndex
from app.schemas import DocumentListResponse, DocumentSummary

router = APIRouter()


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
