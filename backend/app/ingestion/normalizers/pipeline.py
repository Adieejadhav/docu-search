"""
File: backend/app/ingestion/normalizers/pipeline.py
Purpose: Public entrypoint for parser-output normalization.
"""

from __future__ import annotations

from app.ingestion.normalizers.block_schema import ParsedDocument
from app.ingestion.normalizers.document_normalizer import (
    DEFAULT_DOCUMENT_NORMALIZER,
    DocumentNormalizer,
)


def normalize_document(document: ParsedDocument) -> ParsedDocument:
    return DEFAULT_DOCUMENT_NORMALIZER.normalize(document)


__all__ = [
    "DocumentNormalizer",
    "normalize_document",
]
