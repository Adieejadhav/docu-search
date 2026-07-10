"""
File: backend/app/services/admin_service.py
Purpose: Coordinates admin user actions.
"""

from __future__ import annotations

from app.core.exceptions import RetrievalError
from app.repositories import PgVectorIndexStats
from app.repositories import DocumentRepository


class AdminService:
    """Application service for admin operations."""

    def __init__(self, *, document_repository: DocumentRepository) -> None:
        self.document_repository = document_repository

    def clear_index(self, *, confirm: bool) -> PgVectorIndexStats:
        if not confirm:
            raise RetrievalError(
                "Index clear requires confirm=true",
                code="INDEX_CLEAR_NOT_CONFIRMED",
            )

        return self.document_repository.clear_index()
