"""
Compatibility wrapper for the config-owned environment loader.

New code should import environment-aware settings from app.core.config.
"""

from __future__ import annotations

from app.core.config import _load_env_file_without_dependency, load_environment

__all__ = [
    "_load_env_file_without_dependency",
    "load_environment",
]
