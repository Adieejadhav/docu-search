"""
File: backend/app/ingestion/chunking/chunker.py
Purpose: Public chunking pipeline entry points.
"""

from __future__ import annotations

from app.ingestion.chunking.chunk_schema import ChunkedDocument
from app.ingestion.normalizers.block_schema import ParsedDocument

from .strategies.parent_child_chunker import StructureAwareParentChildChunker


DEFAULT_CHUNKER = StructureAwareParentChildChunker()


def chunk_document(document: ParsedDocument) -> ChunkedDocument:
    return DEFAULT_CHUNKER.chunk(document)
