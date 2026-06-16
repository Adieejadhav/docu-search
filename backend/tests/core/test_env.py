from __future__ import annotations

import os

from app.core.env import _load_env_file_without_dependency, load_environment


def test_load_environment_finds_parent_env_without_overriding(
    monkeypatch,
    tmp_path,
):
    project_root = tmp_path / "project"
    backend_dir = project_root / "backend"
    backend_dir.mkdir(parents=True)
    env_path = project_root / ".env"
    env_path.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://example",
                "LOCAL_EMBEDDING_DIMENSIONS=384",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(backend_dir)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("LOCAL_EMBEDDING_DIMENSIONS", "999")

    loaded_path = load_environment()

    assert loaded_path == env_path
    assert os.getenv("DATABASE_URL") == "postgresql://example"
    assert os.getenv("LOCAL_EMBEDDING_DIMENSIONS") == "999"


def test_dependency_free_env_loader_handles_simple_values(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# ignored",
                "DATABASE_URL=postgresql://example",
                "export OLLAMA_MODEL='gpt-oss:120b-cloud'",
                'LOCAL_EMBEDDING_DEVICE="cpu"',
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("LOCAL_EMBEDDING_DEVICE", raising=False)

    _load_env_file_without_dependency(env_path)

    assert os.getenv("DATABASE_URL") == "postgresql://example"
    assert os.getenv("OLLAMA_MODEL") == "gpt-oss:120b-cloud"
    assert os.getenv("LOCAL_EMBEDDING_DEVICE") == "cpu"
