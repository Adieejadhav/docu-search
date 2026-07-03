"""
File: backend/app/search/service.py
Purpose: Coordinates search and RAG answer use cases outside the HTTP route layer.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from app.indexing import PgVectorChunkIndex
from app.rag import RagAnswerer
from app.rag.traces import RagTraceStore
from app.schemas import (
    AskResponse,
    RetrievedChunkResponse,
    SearchRequest,
    SearchResponse,
)
from app.search.retrieval import RetrievalResult


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


def metadata_filters_from_request(request: SearchRequest) -> dict[str, str]:
    filters = {
        "file_name": request.file_name,
        "file_type": request.file_type,
        "document_id": request.document_id,
    }
    return {key: value for key, value in filters.items() if value}


def search_response_from_result(result: RetrievalResult) -> SearchResponse:
    return SearchResponse(
        query=result.query,
        embedding_model=result.embedding_model,
        top_k=result.top_k,
        results=[
            RetrievedChunkResponse(
                rank=item.rank,
                score=item.score,
                document_id=item.child_chunk.document_id,
                file_name=item.metadata.get("file_name"),
                file_type=item.metadata.get("file_type"),
                source_refs=(
                    item.child_chunk.source_refs or item.parent_chunk.source_refs
                ),
                parent_path=(
                    item.child_chunk.parent_path or item.parent_chunk.parent_path
                ),
                child_chunk_id=item.child_chunk.id,
                parent_chunk_id=item.parent_chunk.id,
                child_text=item.child_chunk.text,
                parent_text=item.parent_chunk.text,
            )
            for item in result.results
        ],
        metadata=result.metadata,
    )


def duration_ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)
