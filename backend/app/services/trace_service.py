from __future__ import annotations

from app.core.exceptions import RetrievalError
from app.rag.traces import RagTraceRecord, RagTraceStore
from app.schemas import (
    RagTraceDeleteResponse,
    RagTraceDetail,
    RagTraceListResponse,
    RagTraceSummary,
    SearchResponse,
)


class TraceService:
    """
    Coordinates admin-facing RAG trace inspection and cleanup.
    """

    def __init__(self, *, store: RagTraceStore) -> None:
        self.store = store

    def list_traces(self, *, limit: int, offset: int) -> RagTraceListResponse:
        trace_list = self.store.list_traces(limit=limit, offset=offset)
        return RagTraceListResponse(
            total=trace_list.total,
            limit=trace_list.limit,
            offset=trace_list.offset,
            traces=[trace_summary(trace) for trace in trace_list.traces],
        )

    def get_trace(self, trace_id: str) -> RagTraceDetail:
        trace = self.store.get_trace(trace_id)
        if trace is None:
            raise RetrievalError(
                "RAG trace was not found",
                code="RAG_TRACE_NOT_FOUND",
                details={"trace_id": trace_id},
            )

        return trace_detail(trace)

    def clear_traces(self) -> RagTraceDeleteResponse:
        deleted_count = self.store.delete_traces()
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
