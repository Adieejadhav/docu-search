from __future__ import annotations

from app.cli import clear_database


def test_clear_database_requires_explicit_confirmation(capsys):
    result = clear_database.main(["--database-url", "postgresql://example/db"])

    captured = capsys.readouterr()

    assert result == 2
    assert "Refusing to clear database without --yes" in captured.err


def test_default_migration_path_points_to_pgvector_migration():
    migration_path = clear_database.default_migration_path()

    assert migration_path.name == "001_pgvector_chunk_index.sql"
    assert migration_path.is_file()
