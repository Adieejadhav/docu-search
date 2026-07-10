"""
File: backend/app/rag/answer_generator.py
Purpose: Generates RAG answers through the configured LLM integration.
"""

from __future__ import annotations

from app.integrations.llm import OllamaChatClient


class AnswerGenerator:
    """Thin generation boundary around the LLM client."""

    def __init__(self, *, llm_client: OllamaChatClient) -> None:
        self.llm_client = llm_client

    def generate(self, messages: list[dict[str, str]]) -> str:
        return self.llm_client.generate(messages)
