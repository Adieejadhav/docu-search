"""
File: backend/app/rag/prompt_builder.py
Purpose: Builds RAG LLM prompts from query and context text.
"""

from __future__ import annotations


class RagPromptBuilder:
    """Preserves the existing grounded answer prompt contract."""

    SYSTEM_PROMPT = (
        "You are a document search assistant. Answer only from the provided "
        "retrieved context. If the context is insufficient, say that the "
        "answer is not available in the indexed documents. Cite sources using "
        "only plain bracketed source numbers like [1] or [2]. Do not use any "
        "other citation format."
    )

    def build_messages(self, *, query: str, context: str) -> list[dict[str, str]]:
        user_prompt = (
            f"Question:\n{query}\n\n"
            f"Retrieved context:\n{context}\n\n"
            "Answer with concise, grounded wording and include citations."
        )
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
