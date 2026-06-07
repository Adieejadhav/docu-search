"""
File: backend/app/ingestion/normalizers/metadata_normalizer.py
Purpose: Normalizes metadata into JSON-safe, predictable dictionaries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any


class MetadataNormalizer:
    """
    Converts parser metadata into values that are safe to serialize and inspect.
    """

    def normalize(self, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        if not metadata:
            return {}

        normalized: dict[str, Any] = {}

        for key, value in metadata.items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue

            normalized[normalized_key] = self._normalize_value(value)

        return normalized

    def _normalize_value(self, value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value

        if isinstance(value, datetime | date | time):
            return value.isoformat()

        if isinstance(value, Decimal):
            return str(value)

        if isinstance(value, Path):
            return str(value)

        if isinstance(value, Mapping):
            return self.normalize(value)

        if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            return [self._normalize_value(item) for item in value]

        if isinstance(value, set | frozenset):
            return sorted(self._normalize_value(item) for item in value)

        return str(value)
