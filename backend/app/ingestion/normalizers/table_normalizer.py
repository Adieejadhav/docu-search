"""
File: backend/app/ingestion/normalizers/table_normalizer.py
Purpose: Normalizes table-block text and lightweight table metadata.
"""

from __future__ import annotations

from typing import Any


class TableNormalizer:
    """
    Adds consistent table metadata without reparsing source documents.
    """

    def normalize_metadata(self, text: str, metadata: dict[str, Any]) -> dict[str, Any]:
        normalized_metadata = dict(metadata)

        if "format" not in normalized_metadata:
            normalized_metadata["format"] = "table"

        inferred_shape = self._infer_markdown_table_shape(text)
        if inferred_shape is not None:
            row_count, column_count = inferred_shape
            normalized_metadata.setdefault("rows", row_count)
            normalized_metadata.setdefault("columns", column_count)

        return normalized_metadata

    def _infer_markdown_table_shape(self, text: str) -> tuple[int, int] | None:
        rows = [
            self._split_markdown_table_row(line)
            for line in text.splitlines()
            if line.strip().startswith("|") and line.strip().endswith("|")
        ]
        rows = [row for row in rows if row]

        if len(rows) < 2:
            return None

        data_rows = rows
        if self._is_separator_row(rows[1]):
            data_rows = [rows[0], *rows[2:]]

        column_count = max(len(row) for row in rows)
        return len(data_rows), column_count

    def _split_markdown_table_row(self, line: str) -> list[str]:
        stripped = line.strip().strip("|")
        return [cell.strip() for cell in stripped.split("|")]

    def _is_separator_row(self, row: list[str]) -> bool:
        return all(cell.replace("-", "").replace(":", "").strip() == "" for cell in row)
