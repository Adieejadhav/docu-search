from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_chat_service
from app.chat import ChatService
from app.schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatSessionCreateRequest,
    ChatSessionDeleteResponse,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionSummary,
)
from app.search.service import metadata_filters_from_request

router = APIRouter()


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: ChatService = Depends(get_chat_service),
) -> ChatSessionListResponse:
    return service.list_sessions(limit=limit, offset=offset)


@router.post("/sessions", response_model=ChatSessionSummary)
def create_chat_session(
    request: ChatSessionCreateRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatSessionSummary:
    return service.create_session(title=request.title)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> ChatSessionDetail:
    return service.get_session(session_id)


@router.delete("/sessions/{session_id}", response_model=ChatSessionDeleteResponse)
def delete_chat_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> ChatSessionDeleteResponse:
    return service.delete_session(session_id)


@router.post("/ask", response_model=ChatAskResponse)
def ask_chat(
    request: ChatAskRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatAskResponse:
    return service.ask(
        query=request.query,
        top_k=request.top_k,
        session_id=request.session_id,
        metadata_filters=metadata_filters_from_request(request),
        trace_metadata={"route": "/chat/ask"},
    )


@router.post("/ask/stream")
def ask_chat_stream(
    request: ChatAskRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        service.stream_answer(
            query=request.query,
            top_k=request.top_k,
            session_id=request.session_id,
            metadata_filters=metadata_filters_from_request(request),
            trace_metadata={"route": "/chat/ask/stream"},
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
