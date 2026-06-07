"""
File: backend/app/ingestion/normalizers/text_normalizer.py
Purpose: Provides parser-independent text cleanup for normalized blocks.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.core.constants import BlockType


class TextNormalizer:
    """
    Normalizes text without changing the semantic content extracted by parsers.

    The normalizer keeps newlines where parsers intentionally emitted them, but
    removes byte-order marks, normalizes line endings, and trims trailing spaces.
    """

    WHITESPACE_PATTERN = re.compile(r"[ \t]+")

    def normalize_block_text(self, text: str, block_type: str | BlockType) -> str:
        normalized_text = self.normalize_line_endings(text).lstrip("\ufeff").strip()

        if self._is_block_type(block_type, BlockType.CODE):
            return self._normalize_multiline_text(normalized_text, strip_lines=False)

        if self._is_block_type(block_type, BlockType.TABLE):
            return self._normalize_multiline_text(normalized_text, strip_lines=True)

        if self._is_block_type(block_type, BlockType.JSON):
            return self._normalize_multiline_text(normalized_text, strip_lines=False)

        return self._normalize_prose_text(normalized_text)

    def normalize_parent_path(self, parent_path: Iterable[str]) -> list[str]:
        normalized_path: list[str] = []

        for item in parent_path:
            normalized_item = self._normalize_prose_text(str(item))
            if normalized_item:
                normalized_path.append(normalized_item)

        return normalized_path

    def normalize_line_endings(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _normalize_prose_text(self, text: str) -> str:
        lines = [
            self.WHITESPACE_PATTERN.sub(" ", line.strip())
            for line in self.normalize_line_endings(text).split("\n")
        ]
        return "\n".join(line for line in lines if line).strip()

    def _normalize_multiline_text(self, text: str, *, strip_lines: bool) -> str:
        lines: list[str] = []

        for line in self.normalize_line_endings(text).split("\n"):
            normalized_line = line.strip() if strip_lines else line.rstrip()
            lines.append(normalized_line)

        return "\n".join(lines).strip()

    def _is_block_type(self, value: str | BlockType, expected: BlockType) -> bool:
        return value == expected or value == expected.value
