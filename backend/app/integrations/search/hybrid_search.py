"""
File: backend/app/integrations/search/hybrid_search.py
Purpose: Merges and ranks vector and lexical search candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any


@dataclass(frozen=True)
class HybridSearchWeights:
    vector: float
    lexical: float
    phrase: float


class HybridSearchRanker:
    """Preserves the existing hybrid candidate merge and scoring behavior."""

    def __init__(
        self,
        *,
        weights: HybridSearchWeights,
        max_hybrid_candidates: int,
    ) -> None:
        self.weights = weights
        self.max_hybrid_candidates = max_hybrid_candidates

    def merge_and_rerank_rows(
        self,
        *,
        query: str,
        vector_rows: list[dict[str, Any]],
        lexical_rows: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        has_lexical_hits = False

        for source_name, rows in (("vector", vector_rows), ("lexical", lexical_rows)):
            for source_rank, row in enumerate(rows, start=1):
                row_key = str(row["child_id"])
                existing = merged.get(row_key)
                if existing is None:
                    existing = dict(row)
                    existing["vector_rank"] = None
                    existing["lexical_rank"] = None
                    merged[row_key] = existing

                existing["vector_score"] = max(
                    float(existing.get("vector_score") or 0.0),
                    float(row.get("vector_score") or 0.0),
                )
                existing["lexical_score"] = max(
                    float(existing.get("lexical_score") or 0.0),
                    float(row.get("lexical_score") or 0.0),
                )
                if source_name == "vector":
                    existing["vector_rank"] = source_rank
                else:
                    existing["lexical_rank"] = source_rank
                    has_lexical_hits = True

        reranked_rows = list(merged.values())
        for row in reranked_rows:
            row["score"] = self.hybrid_score(
                query=query,
                row=row,
                has_lexical_hits=has_lexical_hits,
            )

        reranked_rows.sort(
            key=lambda row: (
                float(row["score"]),
                float(row.get("vector_score") or 0.0),
                -(row.get("vector_rank") or self.max_hybrid_candidates + 1),
            ),
            reverse=True,
        )
        return reranked_rows[:top_k]

    def hybrid_score(
        self,
        *,
        query: str,
        row: dict[str, Any],
        has_lexical_hits: bool,
    ) -> float:
        vector_score = float(row.get("vector_score") or 0.0)
        lexical_score = float(row.get("lexical_score") or 0.0)
        if not has_lexical_hits:
            return vector_score

        lexical_component = min(lexical_score * 8.0, 1.0)
        phrase_component = self.phrase_overlap_score(query=query, row=row)
        combined = (
            (self.weights.vector * vector_score)
            + (self.weights.lexical * lexical_component)
            + (self.weights.phrase * phrase_component)
        )
        return min(round(combined, 12), 1.0)

    def phrase_overlap_score(self, *, query: str, row: dict[str, Any]) -> float:
        searchable_text = " ".join(
            [
                str(row.get("file_name") or ""),
                json.dumps(row.get("child_json") or {}, ensure_ascii=False),
                json.dumps(row.get("parent_json") or {}, ensure_ascii=False),
            ]
        )
        query_tokens = meaningful_tokens(query)
        if not query_tokens:
            return 0.0

        text_tokens = set(meaningful_tokens(searchable_text))
        if not text_tokens:
            return 0.0

        matched_tokens = sum(1 for token in query_tokens if token in text_tokens)
        return matched_tokens / len(query_tokens)


def meaningful_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "be",
        "can",
        "do",
        "does",
        "for",
        "how",
        "is",
        "it",
        "of",
        "or",
        "should",
        "the",
        "to",
        "what",
        "when",
        "which",
        "who",
    }
    return [singularize_token(token) for token in tokens if token not in stop_words]


def singularize_token(token: str) -> str:
    if len(token) > 3 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token
