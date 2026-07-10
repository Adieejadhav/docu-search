"""
File: backend/app/rag/citation_validator.py
Purpose: Builds and validates RAG citation payloads.
"""

from __future__ import annotations

from typing import Any

from app.rag.retrieval import RetrievalResult


class CitationValidator:
    """
    Produces the existing citation payload shape.

    The current implementation is intentionally permissive and preserves
    historical behavior. Later phases can add stricter generated-answer
    citation validation behind this boundary.
    """

    def citations(self, retrieval_result: RetrievalResult) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for item in retrieval_result.results:
            child = item.child_chunk
            parent = item.parent_chunk
            citations.append(
                {
                    "rank": item.rank,
                    "score": item.score,
                    "file_name": item.metadata.get("file_name"),
                    "file_type": item.metadata.get("file_type"),
                    "source_refs": child.source_refs or parent.source_refs,
                    "parent_path": child.parent_path or parent.parent_path,
                    "child_chunk_id": child.id,
                    "parent_chunk_id": parent.id,
                }
            )

        return citations
