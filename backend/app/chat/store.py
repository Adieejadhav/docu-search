"""
File: backend/app/chat/store.py
Purpose: Persists chat sessions and messages for the document chat UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import json
import os
from typing import Any, Literal
from uuid import uuid4

from app.core.env import load_environment
from app.core.exceptions import RetrievalError
from app.db.connection import connect_postgres

ChatRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class ChatSessionRecord:
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ChatMessageRecord:
    id: str
    session_id: str
    role: ChatRole
    content: str
    trace_id: str | None
    llm_model: str | None
    latency_ms: float | None
    sources: list[dict[str, Any]]
    created_at: datetime


@dataclass(frozen=True)
class ChatSessionWithMessages:
    session: ChatSessionRecord
    messages: list[ChatMessageRecord]


@dataclass(frozen=True)
class ChatSessionList:
    total: int
    limit: int
    offset: int
    sessions: list[ChatSessionRecord]


class ChatStore:
    """
    PostgreSQL-backed chat history store.
    """

    def __init__(self, *, database_url: str | None = None) -> None:
        load_environment()
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise RetrievalError(
                "DATABASE_URL is required for chat history persistence",
                code="DATABASE_URL_MISSING",
            )

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL
                        REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    trace_id TEXT,
                    llm_model TEXT,
                    latency_ms DOUBLE PRECISION,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
                    ON chat_sessions(updated_at DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
                    ON chat_messages(session_id, created_at)
                """
            )

    def create_session(self, *, title: str | None = None) -> ChatSessionRecord:
        self.initialize()
        session_id = str(uuid4())
        cleaned_title = clean_title(title) or "New chat"
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO chat_sessions(id, title)
                VALUES(%s, %s)
                RETURNING
                    id,
                    title,
                    0 AS message_count,
                    created_at,
                    updated_at
                """,
                (session_id, cleaned_title),
            ).fetchone()

        return self._session_from_row(row)

    def ensure_session(
        self,
        *,
        session_id: str | None,
        title: str | None,
    ) -> ChatSessionRecord:
        if session_id:
            session = self.get_session(session_id)
            if session is None:
                raise RetrievalError(
                    "Chat session was not found",
                    code="CHAT_SESSION_NOT_FOUND",
                    details={"session_id": session_id},
                )
            return session.session

        return self.create_session(title=title)

    def list_sessions(self, *, limit: int = 30, offset: int = 0) -> ChatSessionList:
        self.initialize()
        with self._connect() as connection:
            total_row = connection.execute(
                "SELECT COUNT(*) AS count FROM chat_sessions"
            ).fetchone()
            rows = connection.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    COUNT(m.id) AS message_count,
                    s.created_at,
                    s.updated_at
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON m.session_id = s.id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()

        return ChatSessionList(
            total=int(total_row["count"]),
            limit=limit,
            offset=offset,
            sessions=[self._session_from_row(row) for row in rows],
        )

    def get_session(self, session_id: str) -> ChatSessionWithMessages | None:
        self.initialize()
        with self._connect() as connection:
            session_row = connection.execute(
                """
                SELECT
                    s.id,
                    s.title,
                    COUNT(m.id) AS message_count,
                    s.created_at,
                    s.updated_at
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON m.session_id = s.id
                WHERE s.id = %s
                GROUP BY s.id
                """,
                (session_id,),
            ).fetchone()
            if session_row is None:
                return None

            message_rows = connection.execute(
                """
                SELECT *
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at, id
                """,
                (session_id,),
            ).fetchall()

        return ChatSessionWithMessages(
            session=self._session_from_row(session_row),
            messages=[self._message_from_row(row) for row in message_rows],
        )

    def add_message(
        self,
        *,
        session_id: str,
        role: ChatRole,
        content: str,
        trace_id: str | None = None,
        llm_model: str | None = None,
        latency_ms: float | None = None,
        sources: list[dict[str, Any]] | None = None,
    ) -> ChatMessageRecord:
        self.initialize()
        message_id = str(uuid4())
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO chat_messages(
                    id,
                    session_id,
                    role,
                    content,
                    trace_id,
                    llm_model,
                    latency_ms,
                    sources
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING *
                """,
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    trace_id,
                    llm_model,
                    latency_ms,
                    self._dumps(sources or []),
                ),
            ).fetchone()
            connection.execute(
                """
                UPDATE chat_sessions
                SET updated_at = NOW(),
                    title = CASE
                        WHEN title = 'New chat' AND %s <> '' THEN %s
                        ELSE title
                    END
                WHERE id = %s
                """,
                (content[:80], content[:80], session_id),
            )

        return self._message_from_row(row)

    def delete_session(self, session_id: str) -> bool:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "DELETE FROM chat_sessions WHERE id = %s RETURNING id",
                (session_id,),
            ).fetchone()
        return row is not None

    def _connect(self) -> Any:
        return connect_postgres(
            self.database_url,
            package_error_message=(
                "The psycopg[binary] package is required for chat history persistence"
            ),
        )

    def _session_from_row(self, row: dict[str, Any]) -> ChatSessionRecord:
        return ChatSessionRecord(
            id=row["id"],
            title=row["title"],
            message_count=int(row["message_count"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _message_from_row(self, row: dict[str, Any]) -> ChatMessageRecord:
        latency_ms = row["latency_ms"]
        return ChatMessageRecord(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            trace_id=row["trace_id"],
            llm_model=row["llm_model"],
            latency_ms=float(latency_ms) if latency_ms is not None else None,
            sources=self._loads(row["sources"]),
            created_at=row["created_at"],
        )

    def _dumps(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    def _loads(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        return json.loads(value) if isinstance(value, str) else value


def clean_title(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:160] if cleaned else None
