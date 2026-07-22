from __future__ import annotations

import pytest

from app.integrations.database import DatabasePool


def test_database_pool_reuses_connections_and_commits_successful_work():
    created: list[_FakeConnection] = []

    def factory(_database_url: str) -> _FakeConnection:
        connection = _FakeConnection()
        created.append(connection)
        return connection

    pool = DatabasePool(
        database_url="postgresql://example/db",
        max_size=1,
        connection_factory=factory,
    )

    with pool.connection() as first:
        first.execute("SELECT 1")
    with pool.connection() as second:
        second.execute("SELECT 2")

    assert first is second
    assert len(created) == 1
    assert first.commits == 2
    assert first.rollbacks == 0


def test_database_pool_rolls_back_failed_work_and_closes_idle_connections():
    connection = _FakeConnection()
    pool = DatabasePool(
        database_url="postgresql://example/db",
        connection_factory=lambda _: connection,
    )

    with pytest.raises(RuntimeError):
        with pool.connection():
            raise RuntimeError("boom")
    pool.close()

    assert connection.rollbacks == 1
    assert connection.closed is True


def test_database_pool_does_not_consume_slot_when_connection_creation_fails():
    attempts = 0
    good_connection = _FakeConnection()

    def factory(_database_url: str) -> _FakeConnection:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("cannot connect")
        return good_connection

    pool = DatabasePool(
        database_url="postgresql://example/db",
        max_size=1,
        connection_factory=factory,
    )

    with pytest.raises(RuntimeError):
        with pool.connection():
            pass
    with pool.connection() as connection:
        connection.execute("SELECT 1")

    assert connection is good_connection
    assert attempts == 2


class _FakeConnection:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True
