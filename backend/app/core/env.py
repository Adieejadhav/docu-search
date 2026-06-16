"""
File: backend/app/core/env.py
Purpose: Loads local environment configuration for CLI and service entry points.
"""

from __future__ import annotations

import os
from pathlib import Path


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
