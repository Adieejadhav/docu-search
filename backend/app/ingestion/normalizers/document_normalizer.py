"""
File: backend/app/ingestion/normalizers/document_normalizer.py
Purpose: Provides the parser-independent document normalization pipeline.
"""

from __future__ import annotations

from typing import Any

from app.core.constants import (
    BlockType,
    NORMALIZED_DOCUMENT_SCHEMA_VERSION,
)
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument
from app.ingestion.normalizers.metadata_normalizer import MetadataNormalizer
from app.ingestion.normalizers.source_location_normalizer import (
    SourceLocationNormalizer,
)
from app.ingestion.normalizers.table_normalizer import TableNormalizer
from app.ingestion.normalizers.text_normalizer import TextNormalizer
from app.ingestion.validators.block_validator import validate_parsed_document


class DocumentNormalizer:
    """
    Normalizes parser output into the stable contract consumed by chunking.
    """

    def __init__(
        self,
        *,
        text_normalizer: TextNormalizer | None = None,
        metadata_normalizer: MetadataNormalizer | None = None,
        source_location_normalizer: SourceLocationNormalizer | None = None,
        table_normalizer: TableNormalizer | None = None,
    ) -> None:
        self._text_normalizer = text_normalizer or TextNormalizer()
        self._metadata_normalizer = metadata_normalizer or MetadataNormalizer()
        self._source_location_normalizer = (
            source_location_normalizer or SourceLocationNormalizer()
        )
        self._table_normalizer = table_normalizer or TableNormalizer()

    def normalize(self, document: ParsedDocument) -> ParsedDocument:
        normalized_blocks = [
            self.normalize_block(block, order=order)
            for order, block in enumerate(document.blocks)
        ]
        normalized_metadata = self._normalize_document_metadata(document.metadata)

        normalized_document = ParsedDocument(
            title=self._text_normalizer.normalize_block_text(
                document.title,
                BlockType.PARAGRAPH,
            ),
            file_name=document.file_name,
            file_type=document.file_type,
            source_path=document.source_path,
            blocks=normalized_blocks,
            metadata=normalized_metadata,
        )

        return validate_parsed_document(normalized_document)

    def normalize_block(self, block: DocumentBlock, *, order: int) -> DocumentBlock:
        block_text = self._text_normalizer.normalize_block_text(
            block.text,
            block.block_type,
        )
        block_metadata = self._metadata_normalizer.normalize(block.metadata)
        block_metadata = self._add_source_reference(block, block_metadata)

        if self._is_block_type(block.block_type, BlockType.TABLE):
            block_metadata = self._table_normalizer.normalize_metadata(
                block_text,
                block_metadata,
            )

        return DocumentBlock(
            id=block.id,
            block_type=block.block_type,
            text=block_text,
            order=order,
            level=block.level,
            parent_path=self._text_normalizer.normalize_parent_path(block.parent_path),
            source_location=block.source_location,
            metadata=block_metadata,
        )

    def _normalize_document_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        normalized_metadata = self._metadata_normalizer.normalize(metadata)
        normalized_metadata.setdefault(
            "normalized_schema_version",
            NORMALIZED_DOCUMENT_SCHEMA_VERSION,
        )
        return normalized_metadata

    def _add_source_reference(
        self,
        block: DocumentBlock,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        source_ref = self._source_location_normalizer.source_ref(block.source_location)
        if source_ref is None:
            return metadata

        normalized_metadata = dict(metadata)
        normalized_metadata.setdefault("source_ref", source_ref)
        return normalized_metadata

    def _is_block_type(self, value: str | BlockType, expected: BlockType) -> bool:
        return value == expected or value == expected.value


DEFAULT_DOCUMENT_NORMALIZER = DocumentNormalizer()


def normalize_parsed_document(document: ParsedDocument) -> ParsedDocument:
    return DEFAULT_DOCUMENT_NORMALIZER.normalize(document)
