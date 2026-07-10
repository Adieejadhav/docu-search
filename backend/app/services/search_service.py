from __future__ import annotations

from time import perf_counter
from typing import Any

from app.repositories import PgVectorChunkIndex
from app.rag import RagAnswerer
from app.rag.traces import RagTraceStore
from app.schemas import AskResponse, SearchResponse
from app.services.search_mapping import duration_ms, search_response_from_result


class SearchService:
    """
    Application service for document search and one-shot RAG answers.
    """

    def __init__(
        self,
        *,
        index: PgVectorChunkIndex,
        answerer: RagAnswerer,
        trace_store: RagTraceStore,
    ) -> None:
        self.index = index
        self.answerer = answerer
        self.trace_store = trace_store

    def search(
        self,
        *,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None = None,
    ) -> SearchResponse:
        result = self.index.retrieve(
            query,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )
        return search_response_from_result(result)

    def ask(
        self,
        *,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> AskResponse:
        retrieval_started = perf_counter()
        retrieval_result = self.index.retrieve(
            query,
            top_k=top_k,
            metadata_filters=metadata_filters,
        )
        retrieval_ms = duration_ms(retrieval_started)

        answer_started = perf_counter()
        answer = self.answerer.answer(retrieval_result)
        answer_ms = duration_ms(answer_started)
        retrieval_response = search_response_from_result(answer.retrieval_result)
        trace = self.trace_store.record_trace(
            query=answer.query,
            answer=answer.answer,
            llm_model=answer.llm_model,
            retrieval=retrieval_response,
            citations=answer.citations,
            retrieval_ms=retrieval_ms,
            answer_ms=answer_ms,
            metadata=trace_metadata or {},
        )
        return AskResponse(
            query=answer.query,
            answer=answer.answer,
            llm_model=answer.llm_model,
            retrieval=retrieval_response,
            citations=answer.citations,
            trace_id=trace.id,
        )
