from __future__ import annotations

from pathlib import Path

from app.integrations.database.migrations import (
    SqlMigrationRunner,
    _checksum,
    _crlf_migration_content,
)


def test_migration_record_accepts_lf_and_crlf_checksums(tmp_path):
    migration = tmp_path / "001_example.sql"
    migration.write_bytes(b"SELECT 1;\r\nSELECT 2;\r\n")

    record = SqlMigrationRunner(
        database_url="postgresql://test",
        migrations_dir=tmp_path,
    )._record_for_file(migration)

    assert record.checksum == _checksum(b"SELECT 1;\nSELECT 2;\n")
    assert _checksum(b"SELECT 1;\r\nSELECT 2;\r\n") in record.compatible_checksums
    assert record.checksum in record.compatible_checksums


def test_runner_updates_legacy_line_ending_checksum(tmp_path):
    migration = tmp_path / "001_example.sql"
    migration.write_bytes(b"SELECT 1;\n")
    canonical_record = SqlMigrationRunner(
        database_url="postgresql://test",
        migrations_dir=tmp_path,
    )._record_for_file(migration)
    legacy_checksum = _checksum(_crlf_migration_content(migration.read_bytes()))
    connection = _FakeConnection(existing={"001": legacy_checksum})

    result = _FakeRunner(tmp_path, connection).apply()

    assert result.applied == []
    assert [record.version for record in result.skipped] == ["001"]
    assert connection.existing["001"] == canonical_record.checksum


class _FakeRunner(SqlMigrationRunner):
    def __init__(self, migrations_dir: Path, connection: _FakeConnection) -> None:
        super().__init__(
            database_url="postgresql://test",
            migrations_dir=migrations_dir,
        )
        self.connection = connection

    def _connect(self) -> _FakeConnection:
        return self.connection


class _FakeConnection:
    def __init__(self, *, existing: dict[str, str]) -> None:
        self.existing = existing

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *args) -> None:
        return None

    def execute(self, sql: str, params: tuple[str, ...] | None = None) -> _FakeResult:
        normalized_sql = " ".join(sql.lower().split())
        if normalized_sql.startswith("select version, checksum"):
            return _FakeResult(
                [
                    {"version": version, "checksum": checksum}
                    for version, checksum in self.existing.items()
                ]
            )
        if normalized_sql.startswith("update schema_migrations"):
            assert params is not None
            checksum, version = params
            self.existing[version] = checksum
        if normalized_sql.startswith("insert into schema_migrations"):
            assert params is not None
            version, _name, checksum = params
            self.existing[version] = checksum
        return _FakeResult([])


class _FakeResult:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, str]]:
        return self.rows
