from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_rag_trace_store
from app.core.exceptions import RetrievalError
from app.rag.traces import RagTraceRecord, RagTraceStore
from app.schemas import (
    RagTraceDeleteResponse,
    RagTraceDetail,
    RagTraceListResponse,
    RagTraceSummary,
    SearchResponse,
)

router = APIRouter()


@router.get("", response_model=RagTraceListResponse)
def list_traces(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    store: RagTraceStore = Depends(get_rag_trace_store),
) -> RagTraceListResponse:
    trace_list = store.list_traces(limit=limit, offset=offset)
    return RagTraceListResponse(
        total=trace_list.total,
        limit=trace_list.limit,
        offset=trace_list.offset,
        traces=[trace_summary(trace) for trace in trace_list.traces],
    )


@router.get("/{trace_id}", response_model=RagTraceDetail)
def get_trace(
    trace_id: str,
    store: RagTraceStore = Depends(get_rag_trace_store),
) -> RagTraceDetail:
    trace = store.get_trace(trace_id)
    if trace is None:
        raise RetrievalError(
            "RAG trace was not found",
            code="RAG_TRACE_NOT_FOUND",
            details={"trace_id": trace_id},
        )

    return trace_detail(trace)


@router.delete("", response_model=RagTraceDeleteResponse)
def clear_traces(
    store: RagTraceStore = Depends(get_rag_trace_store),
) -> RagTraceDeleteResponse:
    deleted_count = store.delete_traces()
    return RagTraceDeleteResponse(status="deleted", deleted_count=deleted_count)


def trace_summary(trace: RagTraceRecord) -> RagTraceSummary:
    return RagTraceSummary(
        id=trace.id,
        query=trace.query,
        answer=trace.answer,
        llm_model=trace.llm_model,
        embedding_model=trace.embedding_model,
        top_k=trace.top_k,
        result_count=trace.result_count,
        retrieval_ms=trace.retrieval_ms,
        answer_ms=trace.answer_ms,
        total_ms=trace.total_ms,
        created_at=trace.created_at,
    )


def trace_detail(trace: RagTraceRecord) -> RagTraceDetail:
    return RagTraceDetail(
        **trace_summary(trace).model_dump(),
        retrieval=SearchResponse.model_validate(trace.retrieval),
        citations=trace.citations,
        metadata=trace.metadata,
    )
