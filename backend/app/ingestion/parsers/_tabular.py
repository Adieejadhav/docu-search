from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any


def normalize_cell_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, datetime | date | time):
        return value.isoformat()

    if isinstance(value, Decimal):
        return str(value)

    return str(value).strip()


def normalize_row(values: Iterable[Any]) -> list[str]:
    return [normalize_cell_value(value) for value in values]


def row_is_empty(values: Sequence[str]) -> bool:
    return all(not value for value in values)


def dedupe_headers(headers: Sequence[str]) -> list[str]:
    deduped_headers: list[str] = []
    seen_counts: dict[str, int] = {}

    for index, header in enumerate(headers, start=1):
        base_header = header.strip() or f"column_{index}"
        seen_counts[base_header] = seen_counts.get(base_header, 0) + 1

        if seen_counts[base_header] == 1:
            deduped_headers.append(base_header)
        else:
            deduped_headers.append(f"{base_header}_{seen_counts[base_header]}")

    return deduped_headers


def format_key_value_row(headers: Sequence[str], values: Sequence[str]) -> str:
    max_length = max(len(headers), len(values))
    pairs: list[str] = []

    for index in range(max_length):
        header = headers[index] if index < len(headers) else f"column_{index + 1}"
        value = values[index] if index < len(values) else ""

        if value:
            pairs.append(f"{header}: {value}")

    return " | ".join(pairs)


def format_markdown_table(rows: Sequence[Sequence[str]]) -> str:
    normalized_rows = [list(row) for row in rows if not row_is_empty(list(row))]
    if not normalized_rows:
        return ""

    column_count = max(len(row) for row in normalized_rows)
    padded_rows = [row + [""] * (column_count - len(row)) for row in normalized_rows]

    header = [_escape_markdown_cell(value or f"column_{index + 1}") for index, value in enumerate(padded_rows[0])]
    separator = ["---"] * column_count
    body = [
        [_escape_markdown_cell(value) for value in row]
        for row in padded_rows[1:]
    ]

    rendered_rows = [
        f"| {' | '.join(header)} |",
        f"| {' | '.join(separator)} |",
    ]
    rendered_rows.extend(f"| {' | '.join(row)} |" for row in body)

    return "\n".join(rendered_rows)


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()
