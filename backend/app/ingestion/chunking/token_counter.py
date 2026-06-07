"""
File: backend/app/ingestion/chunking/token_counter.py
Purpose: Provides deterministic approximate token counting for chunk boundaries.
"""

from __future__ import annotations

import re


class ApproximateTokenCounter:
    """
    Counts whitespace-delimited tokens.

    This is intentionally dependency-free. It is good enough for deterministic
    ingestion boundaries; model-specific token accounting can be added later at
    the embedding adapter layer.
    """

    TOKEN_PATTERN = re.compile(r"\S+")

    def count(self, text: str) -> int:
        return len(self.TOKEN_PATTERN.findall(text))

    def split(
        self,
        text: str,
        *,
        target_tokens: int,
        overlap_tokens: int = 0,
    ) -> list[str]:
        if target_tokens < 1:
            raise ValueError("target_tokens must be greater than zero")

        if overlap_tokens < 0:
            raise ValueError("overlap_tokens cannot be negative")

        words = self.TOKEN_PATTERN.findall(text)
        if not words:
            return []

        if len(words) <= target_tokens:
            return [" ".join(words)]

        overlap = min(overlap_tokens, target_tokens - 1)
        step = max(1, target_tokens - overlap)
        chunks: list[str] = []

        start = 0
        while start < len(words):
            end = min(len(words), start + target_tokens)
            chunks.append(" ".join(words[start:end]))
            if end == len(words):
                break
            start += step

        return chunks
