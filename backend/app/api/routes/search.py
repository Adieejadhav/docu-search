from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chunk_index, get_rag_answerer
from app.indexing import PgVectorChunkIndex
from app.rag import RagAnswerer
from app.schemas import (
    AskRequest,
    AskResponse,
    RetrievedChunkResponse,
    SearchRequest,
    SearchResponse,
)
from app.search.retrieval import RetrievalResult

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_index(
    request: SearchRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> SearchResponse:
    result = index.retrieve(
        request.query,
        top_k=request.top_k,
        metadata_filters=metadata_filters_from_request(request),
    )
    return search_response_from_result(result)


@router.post("/ask", response_model=AskResponse)
def ask_index(
    request: AskRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
) -> AskResponse:
    retrieval_result = index.retrieve(
        request.query,
        top_k=request.top_k,
        metadata_filters=metadata_filters_from_request(request),
    )
    answer = answerer.answer(retrieval_result)
    return AskResponse(
        query=answer.query,
        answer=answer.answer,
        llm_model=answer.llm_model,
        retrieval=search_response_from_result(answer.retrieval_result),
        citations=answer.citations,
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
