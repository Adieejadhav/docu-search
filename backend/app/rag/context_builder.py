"""
File: backend/app/rag/context_builder.py
Purpose: Builds grounded RAG context text from retrieval results.
"""

from __future__ import annotations

from app.rag.retrieval import RetrievalResult


class RagContextBuilder:
    """Formats retrieved parent context for answer generation."""

    def build(self, retrieval_result: RetrievalResult) -> str:
        sections: list[str] = []
        for item in retrieval_result.results:
            child = item.child_chunk
            parent = item.parent_chunk
            source_refs = ", ".join(child.source_refs or parent.source_refs or [])
            parent_path = " > ".join(child.parent_path or parent.parent_path or [])
            file_name = item.metadata.get("file_name", "")
            header_parts = [
                f"[{item.rank}]",
                f"score={item.score:.4f}",
            ]
            if file_name:
                header_parts.append(f"file={file_name}")
            if source_refs:
                header_parts.append(f"source={source_refs}")
            if parent_path:
                header_parts.append(f"path={parent_path}")

            sections.append(
                "\n".join(
                    [
                        " ".join(header_parts),
                        parent.text.strip(),
                    ]
                )
            )

        return "\n\n".join(sections)
