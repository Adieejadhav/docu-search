"""
File: backend/app/core/config.py
Purpose: Central typed configuration for Docu Search runtime settings.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from app.core.constants import MAX_FILE_SIZE_BYTES


DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS = 2
DEFAULT_LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_LOCAL_EMBEDDING_DIMENSIONS = 384
DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE = 64
DEFAULT_OLLAMA_MODEL = "gpt-oss:120b-cloud"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_TEMPERATURE = 0.0
DEFAULT_API_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:5174",
    "http://localhost:5174",
)
DEFAULT_API_RATE_LIMIT_PER_MINUTE = 120
DEFAULT_MAX_UPLOAD_FILES = 100
DEFAULT_INGESTION_RUN_MODE = "background"
DEFAULT_HYBRID_VECTOR_WEIGHT = 0.62
DEFAULT_HYBRID_LEXICAL_WEIGHT = 0.30
DEFAULT_HYBRID_PHRASE_WEIGHT = 0.08
DEFAULT_LOG_LEVEL = "INFO"


class DatabaseSettings(BaseModel):
    url: str | None = None
    connect_timeout_seconds: int = DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS


class EmbeddingSettings(BaseModel):
    provider: str = "local"
    model_name: str = DEFAULT_LOCAL_EMBEDDING_MODEL
    dimensions: int = DEFAULT_LOCAL_EMBEDDING_DIMENSIONS
    batch_size: int = DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE
    device: str | None = None


class LlmSettings(BaseModel):
    host: str = DEFAULT_OLLAMA_HOST
    model_name: str = DEFAULT_OLLAMA_MODEL
    temperature: float = DEFAULT_OLLAMA_TEMPERATURE


class SearchSettings(BaseModel):
    hybrid_vector_weight: float = DEFAULT_HYBRID_VECTOR_WEIGHT
    hybrid_lexical_weight: float = DEFAULT_HYBRID_LEXICAL_WEIGHT
    hybrid_phrase_weight: float = DEFAULT_HYBRID_PHRASE_WEIGHT


class IngestionSettings(BaseModel):
    upload_root: Path | None = None
    run_mode: str = DEFAULT_INGESTION_RUN_MODE
    max_upload_files: int = DEFAULT_MAX_UPLOAD_FILES
    max_upload_file_size_bytes: int = MAX_FILE_SIZE_BYTES


class ApiSettings(BaseModel):
    cors_origins: list[str] = Field(default_factory=lambda: list(DEFAULT_API_CORS_ORIGINS))
    rate_limit_per_minute: int = DEFAULT_API_RATE_LIMIT_PER_MINUTE
    log_level: str = DEFAULT_LOG_LEVEL

    @field_validator("cors_origins")
    @classmethod
    def remove_empty_origins(cls, value: list[str]) -> list[str]:
        return [origin.strip() for origin in value if origin.strip()]

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper() or DEFAULT_LOG_LEVEL


class AppSettings(BaseModel):
    database: DatabaseSettings
    embedding: EmbeddingSettings
    llm: LlmSettings
    search: SearchSettings
    ingestion: IngestionSettings
    api: ApiSettings

    def redacted_database_url(self) -> str | None:
        database_url = self.database.url
        if not database_url:
            return None
        if "@" not in database_url:
            return database_url

        scheme_and_credentials, host = database_url.split("@", 1)
        scheme = scheme_and_credentials.split("://", 1)[0]
        return f"{scheme}://***@{host}"


def load_environment() -> Path | None:
    """
    Load the nearest .env file without overriding explicit process variables.
    """

    if os.getenv("DOCU_SEARCH_SKIP_DOTENV") == "1":
        return None

    for env_path in _candidate_env_paths():
        if env_path.is_file():
            _load_env_file(env_path)
            return env_path

    return None


def get_settings() -> AppSettings:
    load_environment()
    return AppSettings(
        database=DatabaseSettings(
            url=_optional_env("DATABASE_URL"),
            connect_timeout_seconds=_int_env(
                "DATABASE_CONNECT_TIMEOUT_SECONDS",
                DEFAULT_DATABASE_CONNECT_TIMEOUT_SECONDS,
            ),
        ),
        embedding=EmbeddingSettings(
            provider=_str_env("EMBEDDING_PROVIDER", "local"),
            model_name=_str_env("LOCAL_EMBEDDING_MODEL", DEFAULT_LOCAL_EMBEDDING_MODEL),
            dimensions=_int_env(
                "LOCAL_EMBEDDING_DIMENSIONS",
                DEFAULT_LOCAL_EMBEDDING_DIMENSIONS,
            ),
            batch_size=_int_env(
                "LOCAL_EMBEDDING_BATCH_SIZE",
                DEFAULT_LOCAL_EMBEDDING_BATCH_SIZE,
            ),
            device=_optional_env("LOCAL_EMBEDDING_DEVICE"),
        ),
        llm=LlmSettings(
            host=_str_env("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
            model_name=_str_env("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
            temperature=_float_env("OLLAMA_TEMPERATURE", DEFAULT_OLLAMA_TEMPERATURE),
        ),
        search=SearchSettings(
            hybrid_vector_weight=_float_env(
                "HYBRID_VECTOR_WEIGHT",
                DEFAULT_HYBRID_VECTOR_WEIGHT,
            ),
            hybrid_lexical_weight=_float_env(
                "HYBRID_LEXICAL_WEIGHT",
                DEFAULT_HYBRID_LEXICAL_WEIGHT,
            ),
            hybrid_phrase_weight=_float_env(
                "HYBRID_PHRASE_WEIGHT",
                DEFAULT_HYBRID_PHRASE_WEIGHT,
            ),
        ),
        ingestion=IngestionSettings(
            upload_root=_path_env("DOCU_SEARCH_UPLOAD_ROOT"),
            run_mode=_str_env("INGESTION_RUN_MODE", DEFAULT_INGESTION_RUN_MODE),
            max_upload_files=_int_env("MAX_UPLOAD_FILES", DEFAULT_MAX_UPLOAD_FILES),
            max_upload_file_size_bytes=_int_env(
                "MAX_UPLOAD_FILE_SIZE_BYTES",
                MAX_FILE_SIZE_BYTES,
            ),
        ),
        api=ApiSettings(
            cors_origins=_csv_env("API_CORS_ORIGINS", DEFAULT_API_CORS_ORIGINS),
            rate_limit_per_minute=_int_env(
                "API_RATE_LIMIT_PER_MINUTE",
                DEFAULT_API_RATE_LIMIT_PER_MINUTE,
            ),
            log_level=_str_env("LOG_LEVEL", DEFAULT_LOG_LEVEL),
        ),
    )


def reset_settings_cache() -> None:
    return None


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return None
    return value


def _str_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _path_env(name: str) -> Path | None:
    value = _optional_env(name)
    return Path(value) if value else None


def _csv_env(name: str, default: tuple[str, ...]) -> list[str]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return list(default)
    return [part.strip() for part in value.split(",") if part.strip()]


def _candidate_env_paths() -> list[Path]:
    candidates: list[Path] = []

    for start_path in (Path.cwd(), Path(__file__).resolve()):
        for path in (start_path, *start_path.parents):
            candidate = path / ".env"
            if candidate not in candidates:
                candidates.append(candidate)

    return candidates


def _load_env_file(env_path: Path) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_file_without_dependency(env_path)
        return

    load_dotenv(dotenv_path=env_path, override=False)


def _load_env_file_without_dependency(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        key, value = line.split("=", 1)
        key = key.strip()
        value = _clean_env_value(value.strip())
        if key and key not in os.environ:
            os.environ[key] = value


def _clean_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]

    return value
