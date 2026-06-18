"""
File: backend/app/llm/ollama_client.py
Purpose: Provides LLM generation through Ollama.
"""

from __future__ import annotations

import os
from typing import Any

from app.core.exceptions import LLMError
from app.core.env import load_environment


class OllamaChatClient:
    """
    Small production wrapper around Ollama chat generation.
    """

    DEFAULT_MODEL = "gpt-oss:120b-cloud"
    DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        host: str | None = None,
        temperature: float = 0.0,
        client: Any | None = None,
    ) -> None:
        load_environment()
        if not model or not model.strip():
            raise LLMError("Ollama model cannot be empty", code="EMPTY_OLLAMA_MODEL")

        self.model = model.strip()
        self.host = host or os.getenv("OLLAMA_HOST") or self.DEFAULT_HOST
        self.temperature = temperature
        self._client = client

    @property
    def name(self) -> str:
        return f"ollama-{self.model}"

    def generate(self, messages: list[dict[str, str]]) -> str:
        if not messages:
            raise LLMError("LLM messages cannot be empty", code="EMPTY_LLM_MESSAGES")

        self._validate_messages(messages)

        try:
            response = self._get_client().chat(
                model=self.model,
                messages=messages,
                options={"temperature": self.temperature},
                stream=False,
            )
        except Exception as exc:
            raise LLMError(
                "Ollama chat request failed",
                code="OLLAMA_CHAT_FAILED",
                details={"model": self.model, "host": self.host},
            ) from exc

        content = self._extract_content(response)
        if not content:
            raise LLMError(
                "Ollama response did not contain message content",
                code="EMPTY_OLLAMA_RESPONSE",
                details={"model": self.model},
            )

        return content

    def stream(self, messages: list[dict[str, str]]):
        if not messages:
            raise LLMError("LLM messages cannot be empty", code="EMPTY_LLM_MESSAGES")

        self._validate_messages(messages)
        try:
            stream = self._get_client().chat(
                model=self.model,
                messages=messages,
                options={"temperature": self.temperature},
                stream=True,
            )
        except Exception as exc:
            raise LLMError(
                "Ollama streaming chat request failed",
                code="OLLAMA_STREAM_FAILED",
                details={"model": self.model, "host": self.host},
            ) from exc

        for chunk in stream:
            content = self._extract_stream_content(chunk)
            if content:
                yield content

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from ollama import Client
        except ImportError as exc:
            raise LLMError(
                "The ollama package is required for Ollama LLM generation",
                code="OLLAMA_PACKAGE_MISSING",
            ) from exc

        self._client = Client(host=self.host)
        return self._client

    def _validate_messages(self, messages: list[dict[str, str]]) -> None:
        for index, message in enumerate(messages):
            role = message.get("role", "")
            content = message.get("content", "")
            if role not in {"system", "user", "assistant"}:
                raise LLMError(
                    "LLM message has invalid role",
                    code="INVALID_LLM_MESSAGE_ROLE",
                    details={"message_index": index, "role": role},
                )
            if not content.strip():
                raise LLMError(
                    "LLM message content cannot be empty",
                    code="EMPTY_LLM_MESSAGE_CONTENT",
                    details={"message_index": index},
                )

    def _extract_content(self, response: Any) -> str:
        if isinstance(response, dict):
            message = response.get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", "")).strip()

        message = getattr(response, "message", None)
        if isinstance(message, dict):
            return str(message.get("content", "")).strip()

        content = getattr(message, "content", None)
        return str(content or "").strip()

    def _extract_stream_content(self, response: Any) -> str:
        if isinstance(response, dict):
            message = response.get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", ""))

        message = getattr(response, "message", None)
        if isinstance(message, dict):
            return str(message.get("content", ""))

        content = getattr(message, "content", None)
        return str(content or "")
