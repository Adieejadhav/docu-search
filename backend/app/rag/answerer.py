"""
File: backend/app/rag/answerer.py
Purpose: Builds grounded RAG prompts from retrieval results and generates answers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import LLMError
from app.integrations.llm import OllamaChatClient
from app.rag.answer_generator import AnswerGenerator
from app.rag.citation_validator import CitationValidator
from app.rag.context_builder import RagContextBuilder
from app.rag.prompt_builder import RagPromptBuilder
from app.rag.retrieval import RetrievalResult


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

    SYSTEM_PROMPT = RagPromptBuilder.SYSTEM_PROMPT

    def __init__(
        self,
        *,
        llm_client: OllamaChatClient | None = None,
        context_builder: RagContextBuilder | None = None,
        prompt_builder: RagPromptBuilder | None = None,
        answer_generator: AnswerGenerator | None = None,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self.llm_client = llm_client or OllamaChatClient()
        self.context_builder = context_builder or RagContextBuilder()
        self.prompt_builder = prompt_builder or RagPromptBuilder()
        self.answer_generator = answer_generator or AnswerGenerator(
            llm_client=self.llm_client,
        )
        self.citation_validator = citation_validator or CitationValidator()

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
        answer_text = self.answer_generator.generate(messages)
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
        return self.prompt_builder.build_messages(
            query=retrieval_result.query,
            context=self._context_text(retrieval_result),
        )

    def _context_text(self, retrieval_result: RetrievalResult) -> str:
        return self.context_builder.build(retrieval_result)

    def citations(self, retrieval_result: RetrievalResult) -> list[dict[str, Any]]:
        return self.citation_validator.citations(retrieval_result)
