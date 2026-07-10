from __future__ import annotations

from time import perf_counter

from app.schemas import (
    RetrievedChunkResponse,
    SearchRequest,
    SearchResponse,
)
from app.rag.retrieval import RetrievalResult


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
