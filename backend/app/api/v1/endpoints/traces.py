from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_trace_service
from app.schemas import (
    RagTraceDeleteResponse,
    RagTraceDetail,
    RagTraceListResponse,
)
from app.services import TraceService

router = APIRouter()


@router.get("", response_model=RagTraceListResponse)
def list_traces(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: TraceService = Depends(get_trace_service),
) -> RagTraceListResponse:
    return service.list_traces(limit=limit, offset=offset)


@router.get("/{trace_id}", response_model=RagTraceDetail)
def get_trace(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> RagTraceDetail:
    return service.get_trace(trace_id)


@router.delete("", response_model=RagTraceDeleteResponse)
def clear_traces(
    service: TraceService = Depends(get_trace_service),
) -> RagTraceDeleteResponse:
    return service.clear_traces()
