from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.core.constants import BlockType, SupportedFileType
from app.ingestion.normalizers import DocumentNormalizer
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)
from app.ingestion.parsers.text_parser import TextParser


def test_document_normalizer_repairs_order_and_adds_source_refs():
    document = ParsedDocument(
        title="  Example Document  ",
        file_name="example.md",
        file_type=SupportedFileType.MARKDOWN,
        blocks=[
            DocumentBlock(
                block_type=BlockType.HEADING,
                text="  Heading  ",
                order=5,
                level=1,
                source_location=SourceLocation(line_start=10, line_end=10),
            ),
            DocumentBlock(
                block_type=BlockType.PARAGRAPH,
                text="  Body\r\ntext  ",
                order=9,
                parent_path=["  Heading  "],
                source_location=SourceLocation(line_start=12, line_end=13),
            ),
        ],
    )

    normalized = DocumentNormalizer().normalize(document)

    assert normalized.title == "Example Document"
    assert [block.order for block in normalized.blocks] == [0, 1]
    assert normalized.blocks[0].text == "Heading"
    assert normalized.blocks[0].metadata["source_ref"] == "lines:10"
    assert normalized.blocks[1].text == "Body\ntext"
    assert normalized.blocks[1].parent_path == ["Heading"]
    assert normalized.blocks[1].metadata["source_ref"] == "lines:12-13"
    assert normalized.metadata["normalized_schema_version"] == "1.0"


def test_document_normalizer_makes_metadata_json_safe():
    document = ParsedDocument(
        title="Example",
        file_name="example.txt",
        file_type=SupportedFileType.TXT,
        blocks=[
            DocumentBlock(
                block_type=BlockType.PARAGRAPH,
                text="Content",
                order=0,
                metadata={
                    "generated_at": datetime(2026, 5, 31, tzinfo=timezone.utc),
                    "score": Decimal("9.5"),
                    "path": Path("docs/example.txt"),
                    "tags": {"search", "rag"},
                },
            )
        ],
    )

    normalized = DocumentNormalizer().normalize(document)

    metadata = normalized.blocks[0].metadata
    assert metadata["generated_at"] == "2026-05-31T00:00:00+00:00"
    assert metadata["score"] == "9.5"
    assert metadata["path"] == "docs\\example.txt" or metadata["path"] == "docs/example.txt"
    assert metadata["tags"] == ["rag", "search"]


def test_document_normalizer_infers_markdown_table_shape():
    document = ParsedDocument(
        title="Example",
        file_name="example.md",
        file_type=SupportedFileType.MARKDOWN,
        blocks=[
            DocumentBlock(
                block_type=BlockType.TABLE,
                text="| Name | Score |\n| --- | --- |\n| Ada | 98 |",
                order=0,
                metadata={"format": "markdown_table"},
            )
        ],
    )

    normalized = DocumentNormalizer().normalize(document)

    assert normalized.blocks[0].metadata["rows"] == 2
    assert normalized.blocks[0].metadata["columns"] == 2


def test_base_parser_applies_document_normalizer(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("First line   \n\n- item\n", encoding="utf-8")

    document = TextParser().parse(file_path)

    assert document.metadata["normalized_schema_version"] == "1.0"
    assert document.blocks[0].metadata["source_ref"] == "lines:1"
    assert document.blocks[1].metadata["source_ref"] == "lines:3"
