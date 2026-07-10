from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_search_service
from app.schemas import (
    AskRequest,
    AskResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.search_mapping import metadata_filters_from_request
from app.services import SearchService

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_index(
    request: SearchRequest,
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return service.search(
        query=request.query,
        top_k=request.top_k,
        metadata_filters=metadata_filters_from_request(request),
    )


@router.post("/ask", response_model=AskResponse)
def ask_index(
    request: AskRequest,
    service: SearchService = Depends(get_search_service),
) -> AskResponse:
    return service.ask(
        query=request.query,
        top_k=request.top_k,
        metadata_filters=metadata_filters_from_request(request),
        trace_metadata={"route": "/ask"},
    )
