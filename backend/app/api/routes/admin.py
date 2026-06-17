from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chunk_index
from app.core.exceptions import RetrievalError
from app.indexing import PgVectorChunkIndex
from app.schemas import AdminClearIndexRequest, AdminClearIndexResponse

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
