from __future__ import annotations

from app.core.constants import SupportedFileType
from app.ingestion.chunking import ChildChunk, ParentChunk
from app.rag import RagAnswer
from app.rag.retrieval import RetrievedChunk, RetrievalResult
from app.services import SearchService


def test_search_service_returns_mapped_retrieval_response():
    index = _FakeIndex()
    service = SearchService(
        index=index,
        answerer=_FakeAnswerer(),
        trace_store=_FakeTraceStore(),
    )

    response = service.search(
        query="satellite exception",
        top_k=1,
        metadata_filters={"file_name": "policy.md"},
    )

    assert index.last_metadata_filters == {"file_name": "policy.md"}
    assert response.query == "satellite exception"
    assert response.results[0].child_chunk_id == "child-1"
    assert response.results[0].parent_chunk_id == "parent-1"


def test_search_service_records_trace_for_one_shot_answer():
    trace_store = _FakeTraceStore()
    service = SearchService(
        index=_FakeIndex(),
        answerer=_FakeAnswerer(),
        trace_store=trace_store,
    )

    response = service.ask(
        query="Which policy?",
        top_k=1,
        trace_metadata={"route": "/ask"},
    )

    assert response.trace_id == "trace-1"
    assert response.answer == "Policy P-004 mentions the exception [1]."
    assert trace_store.last_metadata == {"route": "/ask"}


class _FakeIndex:
    def __init__(self) -> None:
        self.last_metadata_filters = None

    def retrieve(self, query: str, *, top_k: int, metadata_filters=None):
        self.last_metadata_filters = metadata_filters
        return _retrieval_result(query=query, top_k=top_k)


class _FakeAnswerer:
    def answer(self, retrieval_result: RetrievalResult) -> RagAnswer:
        return RagAnswer(
            query=retrieval_result.query,
            answer="Policy P-004 mentions the exception [1].",
            llm_model="fake-llm",
            retrieval_result=retrieval_result,
            citations=[{"rank": 1, "child_chunk_id": "child-1"}],
        )


class _FakeTrace:
    id = "trace-1"


class _FakeTraceStore:
    def __init__(self) -> None:
        self.last_metadata = None

    def record_trace(self, **kwargs):
        self.last_metadata = kwargs["metadata"]
        return _FakeTrace()


def _retrieval_result(*, query: str, top_k: int) -> RetrievalResult:
    parent = ParentChunk(
        id="parent-1",
        document_id="doc-1",
        parent_index=0,
        text="P-004 password rotation exception context.",
        token_count=6,
        source_block_ids=["block-1"],
        source_refs=["lines:1-2"],
        parent_path=["Policy"],
    )
    child = ChildChunk(
        id="child-1",
        document_id="doc-1",
        parent_chunk_id=parent.id,
        child_index=0,
        text="P-004 satellite mode syncs within 14 days.",
        token_count=7,
        source_block_ids=["block-1"],
        source_refs=["lines:1-2"],
        parent_path=["Policy"],
    )
    return RetrievalResult(
        query=query,
        embedding_model="fake-embedding",
        top_k=top_k,
        results=[
            RetrievedChunk(
                rank=1,
                score=0.99,
                child_chunk=child,
                parent_chunk=parent,
                metadata={
                    "file_name": "policy.md",
                    "file_type": SupportedFileType.MARKDOWN,
                },
            )
        ],
        metadata={"indexed_document_count": 1},
    )
