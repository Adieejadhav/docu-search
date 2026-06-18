from __future__ import annotations

import json
from time import perf_counter

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.dependencies import (
    get_chat_store,
    get_chunk_index,
    get_rag_answerer,
    get_rag_trace_store,
)
from app.api.routes.search import (
    duration_ms,
    metadata_filters_from_request,
    search_response_from_result,
)
from app.chat import ChatMessageRecord, ChatSessionRecord, ChatStore
from app.core.exceptions import RetrievalError
from app.indexing import PgVectorChunkIndex
from app.rag import RagAnswerer
from app.rag.traces import RagTraceStore
from app.schemas import (
    AskResponse,
    ChatAskRequest,
    ChatAskResponse,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionDeleteResponse,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionSummary,
    RetrievedChunkResponse,
)

router = APIRouter()


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    store: ChatStore = Depends(get_chat_store),
) -> ChatSessionListResponse:
    session_list = store.list_sessions(limit=limit, offset=offset)
    return ChatSessionListResponse(
        total=session_list.total,
        limit=session_list.limit,
        offset=session_list.offset,
        sessions=[session_summary(session) for session in session_list.sessions],
    )


@router.post("/sessions", response_model=ChatSessionSummary)
def create_chat_session(
    request: ChatSessionCreateRequest,
    store: ChatStore = Depends(get_chat_store),
) -> ChatSessionSummary:
    return session_summary(store.create_session(title=request.title))


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(
    session_id: str,
    store: ChatStore = Depends(get_chat_store),
) -> ChatSessionDetail:
    session = store.get_session(session_id)
    if session is None:
        raise RetrievalError(
            "Chat session was not found",
            code="CHAT_SESSION_NOT_FOUND",
            details={"session_id": session_id},
        )

    summary = session_summary(session.session)
    return ChatSessionDetail(
        **summary.model_dump(),
        messages=[chat_message_response(message) for message in session.messages],
    )


@router.delete("/sessions/{session_id}", response_model=ChatSessionDeleteResponse)
def delete_chat_session(
    session_id: str,
    store: ChatStore = Depends(get_chat_store),
) -> ChatSessionDeleteResponse:
    deleted = store.delete_session(session_id)
    if not deleted:
        raise RetrievalError(
            "Chat session was not found",
            code="CHAT_SESSION_NOT_FOUND",
            details={"session_id": session_id},
        )

    return ChatSessionDeleteResponse(status="deleted", session_id=session_id)


@router.post("/ask", response_model=ChatAskResponse)
def ask_chat(
    request: ChatAskRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    trace_store: RagTraceStore = Depends(get_rag_trace_store),
    chat_store: ChatStore = Depends(get_chat_store),
) -> ChatAskResponse:
    session = chat_store.ensure_session(
        session_id=request.session_id,
        title=request.query,
    )
    user_message = chat_store.add_message(
        session_id=session.id,
        role="user",
        content=request.query,
    )

    retrieval_started = perf_counter()
    retrieval_result = index.retrieve(
        request.query,
        top_k=request.top_k,
        metadata_filters=metadata_filters_from_request(request),
    )
    retrieval_ms = duration_ms(retrieval_started)

    answer_started = perf_counter()
    answer = answerer.answer(retrieval_result)
    answer_ms = duration_ms(answer_started)
    retrieval_response = search_response_from_result(answer.retrieval_result)
    trace = trace_store.record_trace(
        query=answer.query,
        answer=answer.answer,
        llm_model=answer.llm_model,
        retrieval=retrieval_response,
        citations=answer.citations,
        retrieval_ms=retrieval_ms,
        answer_ms=answer_ms,
        metadata={"route": "/chat/ask", "session_id": session.id},
    )

    assistant_message = chat_store.add_message(
        session_id=session.id,
        role="assistant",
        content=answer.answer,
        trace_id=trace.id,
        llm_model=answer.llm_model,
        latency_ms=round(retrieval_ms + answer_ms, 3),
        sources=[
            source.model_dump(mode="json")
            for source in retrieval_response.results
        ],
    )
    refreshed_session = chat_store.get_session(session.id)

    return ChatAskResponse(
        session=session_summary(
            refreshed_session.session if refreshed_session else session
        ),
        user_message=chat_message_response(user_message),
        assistant_message=chat_message_response(assistant_message),
        answer=AskResponse(
            query=answer.query,
            answer=answer.answer,
            llm_model=answer.llm_model,
            retrieval=retrieval_response,
            citations=answer.citations,
            trace_id=trace.id,
        ),
    )


@router.post("/ask/stream")
def ask_chat_stream(
    request: ChatAskRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    answerer: RagAnswerer = Depends(get_rag_answerer),
    trace_store: RagTraceStore = Depends(get_rag_trace_store),
    chat_store: ChatStore = Depends(get_chat_store),
) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_answer(
            request=request,
            index=index,
            answerer=answerer,
            trace_store=trace_store,
            chat_store=chat_store,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def stream_chat_answer(
    *,
    request: ChatAskRequest,
    index: PgVectorChunkIndex,
    answerer: RagAnswerer,
    trace_store: RagTraceStore,
    chat_store: ChatStore,
):
    retrieval_ms = 0.0
    answer_started = perf_counter()
    answer_parts: list[str] = []
    try:
        session = chat_store.ensure_session(
            session_id=request.session_id,
            title=request.query,
        )
        user_message = chat_store.add_message(
            session_id=session.id,
            role="user",
            content=request.query,
        )
        yield sse_event(
            "session",
            {
                "session": session_summary(session).model_dump(mode="json"),
                "user_message": chat_message_response(user_message).model_dump(mode="json"),
            },
        )

        retrieval_started = perf_counter()
        retrieval_result = index.retrieve(
            request.query,
            top_k=request.top_k,
            metadata_filters=metadata_filters_from_request(request),
        )
        retrieval_ms = duration_ms(retrieval_started)
        retrieval_response = search_response_from_result(retrieval_result)
        yield sse_event(
            "retrieval",
            retrieval_response.model_dump(mode="json"),
        )

        messages = answerer.build_messages(retrieval_result)
        for delta in answerer.llm_client.stream(messages):
            answer_parts.append(delta)
            yield sse_event("delta", {"text": delta})

        answer_text = "".join(answer_parts).strip()
        answer_ms = duration_ms(answer_started)
        trace = trace_store.record_trace(
            query=request.query,
            answer=answer_text,
            llm_model=answerer.llm_client.name,
            retrieval=retrieval_response,
            citations=answerer.citations(retrieval_result),
            retrieval_ms=retrieval_ms,
            answer_ms=answer_ms,
            metadata={"route": "/chat/ask/stream", "session_id": session.id},
        )
        assistant_message = chat_store.add_message(
            session_id=session.id,
            role="assistant",
            content=answer_text,
            trace_id=trace.id,
            llm_model=answerer.llm_client.name,
            latency_ms=round(retrieval_ms + answer_ms, 3),
            sources=[
                source.model_dump(mode="json")
                for source in retrieval_response.results
            ],
        )
        refreshed_session = chat_store.get_session(session.id)
        yield sse_event(
            "complete",
            {
                "session": session_summary(
                    refreshed_session.session if refreshed_session else session
                ).model_dump(mode="json"),
                "assistant_message": chat_message_response(assistant_message).model_dump(
                    mode="json"
                ),
                "trace_id": trace.id,
            },
        )
    except Exception as exc:
        yield sse_event(
            "error",
            {
                "code": getattr(exc, "code", exc.__class__.__name__),
                "message": getattr(exc, "message", str(exc)),
            },
        )


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def session_summary(session: ChatSessionRecord) -> ChatSessionSummary:
    return ChatSessionSummary(
        id=session.id,
        title=session.title,
        message_count=session.message_count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def chat_message_response(message: ChatMessageRecord) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        trace_id=message.trace_id,
        llm_model=message.llm_model,
        latency_ms=message.latency_ms,
        sources=[
            RetrievedChunkResponse.model_validate(source)
            for source in message.sources
        ],
        created_at=message.created_at,
    )
