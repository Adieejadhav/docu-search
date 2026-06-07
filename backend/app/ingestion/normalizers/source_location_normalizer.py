"""
File: backend/app/ingestion/normalizers/source_location_normalizer.py
Purpose: Adds compact, parser-independent source reference metadata.
"""

from __future__ import annotations

from app.ingestion.normalizers.block_schema import SourceLocation


class SourceLocationNormalizer:
    """
    Converts populated SourceLocation fields into a human-readable reference.
    """

    def source_ref(self, source_location: SourceLocation) -> str | None:
        parts: list[str] = []

        if source_location.page_number is not None:
            parts.append(f"page:{source_location.page_number}")

        if source_location.slide_number is not None:
            parts.append(f"slide:{source_location.slide_number}")

        if source_location.sheet_name is not None:
            parts.append(f"sheet:{source_location.sheet_name}")

        line_ref = self._range_ref(
            prefix="lines",
            start=source_location.line_start,
            end=source_location.line_end,
        )
        if line_ref is not None:
            parts.append(line_ref)

        row_ref = self._range_ref(
            prefix="rows",
            start=source_location.row_start,
            end=source_location.row_end,
        )
        if row_ref is not None:
            parts.append(row_ref)

        if not parts:
            return None

        return ";".join(parts)

    def _range_ref(
        self,
        *,
        prefix: str,
        start: int | None,
        end: int | None,
    ) -> str | None:
        if start is None and end is None:
            return None

        if start is None:
            return f"{prefix}:?-{end}"

        if end is None or end == start:
            return f"{prefix}:{start}"

        return f"{prefix}:{start}-{end}"
