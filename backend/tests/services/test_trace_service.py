from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.exceptions import RetrievalError
from app.rag.traces import RagTraceList, RagTraceRecord
from app.services import TraceService


def test_trace_service_lists_and_reads_trace_details():
    store = _FakeTraceStore()
    service = TraceService(store=store)

    listed = service.list_traces(limit=10, offset=0)
    detail = service.get_trace("trace-1")

    assert listed.total == 1
    assert listed.traces[0].id == "trace-1"
    assert detail.retrieval.query == "Which policy?"
    assert detail.citations == [{"rank": 1, "child_chunk_id": "child-1"}]


def test_trace_service_raises_existing_error_for_missing_trace():
    service = TraceService(store=_FakeTraceStore())

    with pytest.raises(RetrievalError) as error:
        service.get_trace("missing")

    assert error.value.code == "RAG_TRACE_NOT_FOUND"


def test_trace_service_clears_traces():
    store = _FakeTraceStore()
    service = TraceService(store=store)

    response = service.clear_traces()

    assert response.status == "deleted"
    assert response.deleted_count == 1


class _FakeTraceStore:
    def __init__(self) -> None:
        self.trace = _trace_record()

    def list_traces(self, *, limit: int, offset: int) -> RagTraceList:
        return RagTraceList(total=1, limit=limit, offset=offset, traces=[self.trace])

    def get_trace(self, trace_id: str) -> RagTraceRecord | None:
        return self.trace if trace_id == self.trace.id else None

    def delete_traces(self) -> int:
        return 1


def _trace_record() -> RagTraceRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return RagTraceRecord(
        id="trace-1",
        query="Which policy?",
        answer="Policy P-004 mentions the exception [1].",
        llm_model="fake-llm",
        embedding_model="fake-embedding",
        top_k=1,
        result_count=1,
        retrieval_ms=2.0,
        answer_ms=3.0,
        total_ms=5.0,
        retrieval={
            "query": "Which policy?",
            "embedding_model": "fake-embedding",
            "top_k": 1,
            "results": [],
            "metadata": {},
        },
        citations=[{"rank": 1, "child_chunk_id": "child-1"}],
        metadata={"route": "/ask"},
        created_at=now,
    )
