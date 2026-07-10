"""
File: backend/app/services/document_service.py
Purpose: Coordinates indexed document user actions.
"""

from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import RetrievalError
from app.repositories import IndexedDocumentChunkSummary, IndexedDocumentSummary
from app.ingestion.jobs import IngestionJobRecord, IngestionJobService
from app.repositories import DocumentRepository


@dataclass(frozen=True)
class DocumentListPage:
    total: int
    limit: int
    offset: int
    documents: list[IndexedDocumentSummary]


@dataclass(frozen=True)
class DocumentChunkPage:
    document: IndexedDocumentSummary
    total: int
    limit: int
    offset: int
    chunks: list[IndexedDocumentChunkSummary]


@dataclass(frozen=True)
class DocumentSourceFile:
    path: Path
    file_name: str
    media_type: str


@dataclass(frozen=True)
class DocumentReindexPlan:
    job: IngestionJobRecord
    run_in_background: bool


class DocumentService:
    """Application service for indexed document workflows."""

    def __init__(self, *, repository: DocumentRepository) -> None:
        self.repository = repository

    def list_documents(self, *, limit: int, offset: int) -> DocumentListPage:
        stats = self.repository.stats()
        return DocumentListPage(
            total=stats.document_count,
            limit=limit,
            offset=offset,
            documents=self.repository.list_documents(limit=limit, offset=offset),
        )

    def get_document_source(self, document_id: str) -> DocumentSourceFile:
        document = self._require_document(document_id)
        if not document.source_path:
            raise RetrievalError(
                "Document source file path is missing",
                code="DOCUMENT_SOURCE_PATH_MISSING",
                details={"document_id": document_id},
            )

        source_path = Path(document.source_path).expanduser()
        if not source_path.is_absolute():
            source_path = source_path.resolve()
        if not source_path.is_file():
            raise RetrievalError(
                "Document source file was not found on disk",
                code="DOCUMENT_SOURCE_FILE_NOT_FOUND",
                details={
                    "document_id": document_id,
                    "source_path": str(source_path),
                },
            )

        media_type, _ = mimetypes.guess_type(document.file_name)
        return DocumentSourceFile(
            path=source_path,
            file_name=document.file_name,
            media_type=media_type or "application/octet-stream",
        )

    def list_document_chunks(
        self,
        document_id: str,
        *,
        limit: int,
        offset: int,
    ) -> DocumentChunkPage:
        document = self._require_document(document_id)
        total, chunks = self.repository.list_document_chunks(
            document_id,
            limit=limit,
            offset=offset,
        )
        return DocumentChunkPage(
            document=document,
            total=total,
            limit=limit,
            offset=offset,
            chunks=chunks,
        )

    def delete_document(self, document_id: str) -> str:
        deleted = self.repository.delete_document(document_id)
        if not deleted:
            raise RetrievalError(
                "Document was not found",
                code="DOCUMENT_NOT_FOUND",
                details={"document_id": document_id},
            )
        return document_id

    def create_reindex_job(
        self,
        document_id: str,
        *,
        ingestion_jobs: IngestionJobService,
    ) -> DocumentReindexPlan:
        document = self._require_document(document_id)
        if not document.source_path:
            raise RetrievalError(
                "Document cannot be re-indexed because source_path is missing",
                code="DOCUMENT_SOURCE_PATH_MISSING",
                details={"document_id": document_id},
            )

        job = ingestion_jobs.create_job(
            source_paths=[Path(document.source_path)],
            source_kind="reindex",
            options={
                "recursive": False,
                "clear_index": False,
                "replace": True,
                "continue_on_error": False,
                "document_id": document_id,
            },
        )
        return DocumentReindexPlan(
            job=job,
            run_in_background=self._ingestion_run_mode() == "background",
        )

    def _require_document(self, document_id: str) -> IndexedDocumentSummary:
        document = self.repository.get_document(document_id)
        if document is None:
            raise RetrievalError(
                "Document was not found",
                code="DOCUMENT_NOT_FOUND",
                details={"document_id": document_id},
            )
        return document

    def _ingestion_run_mode(self) -> str:
        mode = get_settings().ingestion.run_mode.strip().lower()
        if mode not in {"background", "worker"}:
            raise RetrievalError(
                "INGESTION_RUN_MODE must be 'background' or 'worker'",
                code="INVALID_INGESTION_RUN_MODE",
                details={"INGESTION_RUN_MODE": mode},
            )
        return mode
