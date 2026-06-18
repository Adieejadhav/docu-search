"""
File: backend/app/rag/answerer.py
Purpose: Builds grounded RAG prompts from retrieval results and generates answers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import LLMError
from app.llm import OllamaChatClient
from app.search.retrieval import RetrievalResult


class RagAnswer(BaseModel):
    """
    Final answer plus the retrieval result used to ground it.
    """

    model_config = ConfigDict(use_enum_values=True)

    query: str
    answer: str
    llm_model: str
    retrieval_result: RetrievalResult
    citations: list[dict[str, Any]] = Field(default_factory=list)


class RagAnswerer:
    """
    Generates an answer from parent-child retrieval context.
    """

    SYSTEM_PROMPT = (
        "You are a document search assistant. Answer only from the provided "
        "retrieved context. If the context is insufficient, say that the "
        "answer is not available in the indexed documents. Cite sources using "
        "only plain bracketed source numbers like [1] or [2]. Do not use any "
        "other citation format."
    )

    def __init__(self, *, llm_client: OllamaChatClient | None = None) -> None:
        self.llm_client = llm_client or OllamaChatClient()

    def answer(self, retrieval_result: RetrievalResult) -> RagAnswer:
        if not retrieval_result.results:
            return RagAnswer(
                query=retrieval_result.query,
                answer="The answer is not available in the indexed documents.",
                llm_model=self.llm_client.name,
                retrieval_result=retrieval_result,
                citations=[],
            )

        messages = self.build_messages(retrieval_result)
        answer_text = self.llm_client.generate(messages)
        if not answer_text.strip():
            raise LLMError("Generated answer cannot be empty", code="EMPTY_RAG_ANSWER")

        return RagAnswer(
            query=retrieval_result.query,
            answer=answer_text,
            llm_model=self.llm_client.name,
            retrieval_result=retrieval_result,
            citations=self.citations(retrieval_result),
        )

    def build_messages(self, retrieval_result: RetrievalResult) -> list[dict[str, str]]:
        context = self._context_text(retrieval_result)
        user_prompt = (
            f"Question:\n{retrieval_result.query}\n\n"
            f"Retrieved context:\n{context}\n\n"
            "Answer with concise, grounded wording and include citations."
        )
        return [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    def _context_text(self, retrieval_result: RetrievalResult) -> str:
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
