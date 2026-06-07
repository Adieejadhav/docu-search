from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from docx import Document as open_docx
from docx.document import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.constants import BlockType, SupportedFileType, SUPPORTED_DOCX_EXTENSIONS
from app.core.exceptions import ParserError
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument
from app.ingestion.parsers._tabular import format_markdown_table, normalize_row
from app.ingestion.parsers.base import BaseDocumentParser


class DocxParser(BaseDocumentParser):
    """
    Parser for Word .docx documents.

    Paragraphs, headings, list items, and tables are emitted in document order.
    """

    supported_extensions = SUPPORTED_DOCX_EXTENSIONS

    HEADING_STYLE_PATTERN = re.compile(r"^heading\s+(?P<level>[1-6])$", re.IGNORECASE)

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = self.validate_input_file(file_path)
        document = self._open_document(path)
        blocks = self._parse_document(document)
        title = self._extract_title(document, blocks) or self.get_document_title(path)

        return self.build_document(
            path=path,
            title=title,
            file_type=SupportedFileType.DOCX,
            blocks=blocks,
            metadata={
                "core_properties_title": document.core_properties.title or None,
            },
        )

    def _open_document(self, path: Path) -> DocxDocument:
        try:
            return open_docx(str(path))
        except PackageNotFoundError as exc:
            raise ParserError(
                f"Unable to open DOCX file: {path}",
                code="DOCX_OPEN_FAILED",
                details={"file_path": str(path)},
            ) from exc
        except Exception as exc:
            raise ParserError(
                f"Unable to parse DOCX file: {path}",
                code="DOCX_PARSE_FAILED",
                details={"file_path": str(path)},
            ) from exc

    def _parse_document(self, document: DocxDocument) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        heading_stack: dict[int, str] = {}
        table_index = 0

        for item in self._iter_block_items(document):
            if isinstance(item, Paragraph):
                block = self._paragraph_to_block(item, heading_stack)
                if block is None:
                    continue

                blocks.append(block.model_copy(update={"order": len(blocks)}))
                continue

            table_index += 1
            table_text = self._table_to_text(item)
            if not table_text:
                continue

            blocks.append(
                DocumentBlock(
                    block_type=BlockType.TABLE,
                    text=table_text,
                    order=len(blocks),
                    parent_path=self._current_parent_path(heading_stack),
                    metadata={
                        "format": "docx_table",
                        "table_index": table_index,
                        "rows": len(item.rows),
                        "columns": len(item.columns),
                    },
                )
            )

        return blocks

    def _iter_block_items(
        self,
        document: DocxDocument,
    ) -> Iterator[Paragraph | Table]:
        for child in document.element.body.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, document)
            elif child.tag == qn("w:tbl"):
                yield Table(child, document)

    def _paragraph_to_block(
        self,
        paragraph: Paragraph,
        heading_stack: dict[int, str],
    ) -> DocumentBlock | None:
        text = paragraph.text.strip()
        if not text:
            return None

        style_name = paragraph.style.name if paragraph.style is not None else ""
        heading_level = self._heading_level(style_name)

        if heading_level is not None:
            parent_path = [
                heading_stack[level]
                for level in sorted(heading_stack)
                if level < heading_level
            ]
            heading_stack[heading_level] = text

            for existing_level in list(heading_stack):
                if existing_level > heading_level:
                    del heading_stack[existing_level]

            return DocumentBlock(
                block_type=BlockType.HEADING,
                text=text,
                order=0,
                level=heading_level,
                parent_path=parent_path,
                metadata={"style": style_name},
            )

        block_type = (
            BlockType.LIST_ITEM
            if self._is_list_style(style_name)
            else BlockType.PARAGRAPH
        )

        return DocumentBlock(
            block_type=block_type,
            text=text,
            order=0,
            parent_path=self._current_parent_path(heading_stack),
            metadata={"style": style_name},
        )

    def _table_to_text(self, table: Table) -> str:
        rows = [normalize_row(cell.text for cell in row.cells) for row in table.rows]
        return format_markdown_table(rows)

    def _heading_level(self, style_name: str) -> int | None:
        match = self.HEADING_STYLE_PATTERN.match(style_name.strip())
        if match is None:
            return None

        return int(match.group("level"))

    def _is_list_style(self, style_name: str) -> bool:
        normalized_style = style_name.strip().lower()
        return "list" in normalized_style or normalized_style.startswith("bullet")

    def _current_parent_path(self, heading_stack: dict[int, str]) -> list[str]:
        return [
            heading_stack[level]
            for level in sorted(heading_stack)
            if heading_stack.get(level)
        ]

    def _extract_title(
        self,
        document: DocxDocument,
        blocks: list[DocumentBlock],
    ) -> str | None:
        core_title = document.core_properties.title
        if core_title and core_title.strip():
            return core_title.strip()

        for block in blocks:
            if block.block_type == BlockType.HEADING and block.level == 1:
                return block.text

        return None
