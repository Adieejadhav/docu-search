from __future__ import annotations

from app.core.config import (
    DEFAULT_API_CORS_ORIGINS,
    DEFAULT_LOCAL_EMBEDDING_DIMENSIONS,
    DEFAULT_LOCAL_EMBEDDING_MODEL,
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    get_settings,
    reset_settings_cache,
)


def test_settings_use_existing_env_names_and_defaults(monkeypatch):
    monkeypatch.setenv("DOCU_SEARCH_SKIP_DOTENV", "1")
    for name in (
        "DATABASE_URL",
        "LOCAL_EMBEDDING_MODEL",
        "LOCAL_EMBEDDING_DIMENSIONS",
        "LOCAL_EMBEDDING_BATCH_SIZE",
        "LOCAL_EMBEDDING_DEVICE",
        "OLLAMA_HOST",
        "OLLAMA_MODEL",
        "API_CORS_ORIGINS",
        "ADMIN_API_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    reset_settings_cache()

    settings = get_settings()

    assert settings.database.url is None
    assert settings.embedding.model_name == DEFAULT_LOCAL_EMBEDDING_MODEL
    assert settings.embedding.dimensions == DEFAULT_LOCAL_EMBEDDING_DIMENSIONS
    assert settings.embedding.device is None
    assert settings.llm.host == DEFAULT_OLLAMA_HOST
    assert settings.llm.model_name == DEFAULT_OLLAMA_MODEL
    assert settings.api.cors_origins == list(DEFAULT_API_CORS_ORIGINS)
    assert settings.api.admin_api_token is None

    reset_settings_cache()


def test_settings_read_environment_overrides(monkeypatch, tmp_path):
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("DOCU_SEARCH_SKIP_DOTENV", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@localhost/db")
    monkeypatch.setenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "9")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL", "example-embedding")
    monkeypatch.setenv("LOCAL_EMBEDDING_DIMENSIONS", "768")
    monkeypatch.setenv("LOCAL_EMBEDDING_BATCH_SIZE", "12")
    monkeypatch.setenv("LOCAL_EMBEDDING_DEVICE", "cpu")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.example")
    monkeypatch.setenv("OLLAMA_MODEL", "example-llm")
    monkeypatch.setenv("OLLAMA_TEMPERATURE", "0.25")
    monkeypatch.setenv("HYBRID_VECTOR_WEIGHT", "0.5")
    monkeypatch.setenv("HYBRID_LEXICAL_WEIGHT", "0.4")
    monkeypatch.setenv("HYBRID_PHRASE_WEIGHT", "0.1")
    monkeypatch.setenv("DOCU_SEARCH_UPLOAD_ROOT", str(upload_root))
    monkeypatch.setenv("INGESTION_RUN_MODE", "worker")
    monkeypatch.setenv("MAX_UPLOAD_FILES", "7")
    monkeypatch.setenv("MAX_UPLOAD_FILE_SIZE_BYTES", "12345")
    monkeypatch.setenv("API_CORS_ORIGINS", "http://a.example, http://b.example")
    monkeypatch.setenv("API_RATE_LIMIT_PER_MINUTE", "77")
    monkeypatch.setenv("ADMIN_API_TOKEN", "admin-token")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    reset_settings_cache()

    settings = get_settings()

    assert settings.database.url == "postgresql://user:secret@localhost/db"
    assert settings.database.connect_timeout_seconds == 9
    assert settings.embedding.model_name == "example-embedding"
    assert settings.embedding.dimensions == 768
    assert settings.embedding.batch_size == 12
    assert settings.embedding.device == "cpu"
    assert settings.llm.host == "http://ollama.example"
    assert settings.llm.model_name == "example-llm"
    assert settings.llm.temperature == 0.25
    assert settings.search.hybrid_vector_weight == 0.5
    assert settings.search.hybrid_lexical_weight == 0.4
    assert settings.search.hybrid_phrase_weight == 0.1
    assert settings.ingestion.upload_root == upload_root
    assert settings.ingestion.run_mode == "worker"
    assert settings.ingestion.max_upload_files == 7
    assert settings.ingestion.max_upload_file_size_bytes == 12345
    assert settings.api.cors_origins == ["http://a.example", "http://b.example"]
    assert settings.api.rate_limit_per_minute == 77
    assert settings.api.admin_api_token == "admin-token"
    assert settings.api.log_level == "DEBUG"
    assert settings.redacted_database_url() == "postgresql://***@localhost/db"

    reset_settings_cache()
