"""
File: backend/app/chat/service.py
Purpose: Coordinates chat session, retrieval, RAG, and streaming use cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterator

from app.repositories.chat_repository import ChatMessageRecord, ChatSessionRecord, ChatStore
from app.core.exceptions import RetrievalError
from app.repositories import PgVectorChunkIndex
from app.repositories.trace_repository import TraceRepository
from app.rag import RagAnswerer
from app.schemas import (
    AskResponse,
    ChatAskResponse,
    ChatMessageResponse,
    ChatSessionDeleteResponse,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionSummary,
    RetrievedChunkResponse,
)
from app.services.search_mapping import (
    duration_ms,
    search_response_from_result,
)


@dataclass(frozen=True)
class ChatStreamEvent:
    event: str
    data: dict[str, Any]


class ChatService:
    """
    Application service for persisted document chat.
    """

    def __init__(
        self,
        *,
        store: ChatStore,
        index: PgVectorChunkIndex,
        answerer: RagAnswerer,
        trace_store: TraceRepository,
    ) -> None:
        self.store = store
        self.index = index
        self.answerer = answerer
        self.trace_store = trace_store

    def list_sessions(self, *, limit: int, offset: int) -> ChatSessionListResponse:
        session_list = self.store.list_sessions(limit=limit, offset=offset)
        return ChatSessionListResponse(
            total=session_list.total,
            limit=session_list.limit,
            offset=session_list.offset,
            sessions=[session_summary(session) for session in session_list.sessions],
        )

    def create_session(self, *, title: str | None) -> ChatSessionSummary:
        return session_summary(self.store.create_session(title=title))

    def get_session(self, session_id: str) -> ChatSessionDetail:
        session = self.store.get_session(session_id)
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

    def delete_session(self, session_id: str) -> ChatSessionDeleteResponse:
        deleted = self.store.delete_session(session_id)
        if not deleted:
            raise RetrievalError(
                "Chat session was not found",
                code="CHAT_SESSION_NOT_FOUND",
                details={"session_id": session_id},
            )

        return ChatSessionDeleteResponse(status="deleted", session_id=session_id)

    def ask(
        self,
        *,
        query: str,
        top_k: int,
        session_id: str | None,
        metadata_filters: dict[str, Any] | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> ChatAskResponse:
        session = self.store.ensure_session(session_id=session_id, title=query)
        user_message = self.store.add_message(
            session_id=session.id,
            role="user",
            content=query,
        )

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
            metadata={**(trace_metadata or {}), "session_id": session.id},
        )

        assistant_message = self.store.add_message(
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
        refreshed_session = self.store.get_session(session.id)

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

    def stream_answer(
        self,
        *,
        query: str,
        top_k: int,
        session_id: str | None,
        metadata_filters: dict[str, Any] | None = None,
        trace_metadata: dict[str, Any] | None = None,
    ) -> Iterator[ChatStreamEvent]:
        retrieval_ms = 0.0
        answer_started = perf_counter()
        answer_parts: list[str] = []
        try:
            session = self.store.ensure_session(session_id=session_id, title=query)
            user_message = self.store.add_message(
                session_id=session.id,
                role="user",
                content=query,
            )
            yield ChatStreamEvent(
                event="session",
                data={
                    "session": session_summary(session).model_dump(mode="json"),
                    "user_message": chat_message_response(user_message).model_dump(
                        mode="json"
                    ),
                },
            )

            retrieval_started = perf_counter()
            retrieval_result = self.index.retrieve(
                query,
                top_k=top_k,
                metadata_filters=metadata_filters,
            )
            retrieval_ms = duration_ms(retrieval_started)
            retrieval_response = search_response_from_result(retrieval_result)
            yield ChatStreamEvent(
                event="retrieval",
                data=retrieval_response.model_dump(mode="json"),
            )

            messages = self.answerer.build_messages(retrieval_result)
            for delta in self.answerer.llm_client.stream(messages):
                answer_parts.append(delta)
                yield ChatStreamEvent(event="delta", data={"text": delta})

            answer_text = "".join(answer_parts).strip()
            answer_ms = duration_ms(answer_started)
            trace = self.trace_store.record_trace(
                query=query,
                answer=answer_text,
                llm_model=self.answerer.llm_client.name,
                retrieval=retrieval_response,
                citations=self.answerer.citations(retrieval_result),
                retrieval_ms=retrieval_ms,
                answer_ms=answer_ms,
                metadata={**(trace_metadata or {}), "session_id": session.id},
            )
            assistant_message = self.store.add_message(
                session_id=session.id,
                role="assistant",
                content=answer_text,
                trace_id=trace.id,
                llm_model=self.answerer.llm_client.name,
                latency_ms=round(retrieval_ms + answer_ms, 3),
                sources=[
                    source.model_dump(mode="json")
                    for source in retrieval_response.results
                ],
            )
            refreshed_session = self.store.get_session(session.id)
            yield ChatStreamEvent(
                event="complete",
                data={
                    "session": session_summary(
                        refreshed_session.session if refreshed_session else session
                    ).model_dump(mode="json"),
                    "assistant_message": chat_message_response(
                        assistant_message
                    ).model_dump(mode="json"),
                    "trace_id": trace.id,
                },
            )
        except Exception as exc:
            yield ChatStreamEvent(
                event="error",
                data={
                    "code": getattr(exc, "code", exc.__class__.__name__),
                    "message": getattr(exc, "message", str(exc)),
                },
            )


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
