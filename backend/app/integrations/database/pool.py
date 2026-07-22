"""
File: backend/app/integrations/database/pool.py
Purpose: Provides a small reusable PostgreSQL connection pool.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from queue import Empty, LifoQueue
from threading import Lock
from typing import Any

from app.integrations.database.connection import connect_postgres

ConnectionFactory = Callable[[str], Any]


class DatabasePool:
    """Lazy in-process connection pool for psycopg connections."""

    def __init__(
        self,
        *,
        database_url: str,
        max_size: int = 5,
        connection_factory: ConnectionFactory = connect_postgres,
    ) -> None:
        if max_size < 1:
            raise ValueError("max_size must be greater than zero")
        self.database_url = database_url
        self.max_size = max_size
        self.connection_factory = connection_factory
        self._idle: LifoQueue[Any] = LifoQueue(maxsize=max_size)
        self._lock = Lock()
        self._created = 0
        self._closed = False

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connection = self._checkout()
        try:
            yield connection
        except Exception:
            _rollback(connection)
            raise
        else:
            _commit(connection)
        finally:
            self._checkin(connection)

    def close(self) -> None:
        with self._lock:
            self._closed = True
        while not self._idle.empty():
            connection = self._idle.get_nowait()
            _close(connection)

    def _checkout(self) -> Any:
        if self._closed:
            raise RuntimeError("DatabasePool is closed")
        try:
            return self._idle.get_nowait()
        except Empty:
            with self._lock:
                if self._created < self.max_size:
                    self._created += 1
                    should_create = True
                else:
                    should_create = False

            if should_create:
                try:
                    return self.connection_factory(self.database_url)
                except Exception:
                    with self._lock:
                        self._created -= 1
                    raise

        return self._idle.get()

    def _checkin(self, connection: Any) -> None:
        if self._closed or _is_closed(connection):
            _close(connection)
            return
        self._idle.put(connection)


def _commit(connection: Any) -> None:
    commit = getattr(connection, "commit", None)
    if callable(commit):
        commit()


def _rollback(connection: Any) -> None:
    rollback = getattr(connection, "rollback", None)
    if callable(rollback):
        rollback()


def _close(connection: Any) -> None:
    close = getattr(connection, "close", None)
    if callable(close):
        close()


def _is_closed(connection: Any) -> bool:
    return bool(getattr(connection, "closed", False))
