"""
File: backend/app/repositories/document_repository.py
Purpose: Repository boundary for indexed document and chunk persistence.
"""

from __future__ import annotations

from app.repositories.search_repository import (
    IndexedDocumentChunkSummary,
    IndexedDocumentSummary,
    PgVectorChunkIndex,
    PgVectorIndexStats,
)


class DocumentRepository:
    """
    Application-friendly repository for indexed documents.

    This is intentionally a compatibility adapter over PgVectorChunkIndex while
    pgvector-specific SQL is extracted in later phases.
    """

    def __init__(self, *, index: PgVectorChunkIndex) -> None:
        self.index = index

    def stats(self) -> PgVectorIndexStats:
        return self.index.stats()

    def clear_index(self) -> PgVectorIndexStats:
        self.index.clear()
        return self.index.stats()

    def list_documents(
        self,
        *,
        limit: int,
        offset: int,
    ) -> list[IndexedDocumentSummary]:
        return self.index.list_documents(limit=limit, offset=offset)

    def get_document(self, document_id: str) -> IndexedDocumentSummary | None:
        return self.index.get_document(document_id)

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[int, list[IndexedDocumentChunkSummary]]:
        return self.index.list_document_chunks(
            document_id,
            limit=limit,
            offset=offset,
        )

    def delete_document(self, document_id: str) -> bool:
        return self.index.delete_document(document_id)
