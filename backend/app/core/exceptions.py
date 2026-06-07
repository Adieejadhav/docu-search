"""
File: backend/app/core/exceptions.py
Purpose: Defines shared backend exception classes for consistent error handling.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """
    Base exception for all custom backend errors.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}


class ValidationError(AppError):
    """Raised for application/domain validation failures."""


class FileValidationError(ValidationError):
    """Raised when uploaded or local file validation fails."""


class IngestionError(AppError):
    """Base exception for ingestion-related failures."""


class ParserError(IngestionError):
    """Raised when a document parser fails."""


class UnsupportedFileTypeError(ParserError):
    """Raised when no parser supports the given file type."""


class EmptyDocumentError(ParserError):
    """Raised when parsing succeeds but no useful content is found."""


class DocumentBlockValidationError(ValidationError):
    """Raised when normalized document block validation fails."""


class ChunkingError(IngestionError):
    """Raised when parent or child chunk creation fails."""


class EmbeddingError(AppError):
    """Raised when embedding generation fails."""


class RetrievalError(AppError):
    """Raised when document retrieval fails."""


class RerankingError(AppError):
    """Raised when reranking fails."""


class LLMError(AppError):
    """Raised when LLM answer generation fails."""
