from __future__ import annotations

import re
from pathlib import Path

from app.core.constants import (
    BlockType,
    SupportedFileType,
    SUPPORTED_TEXT_EXTENSIONS,
)
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)
from app.ingestion.parsers.base import BaseDocumentParser


class TextParser(BaseDocumentParser):
    """
    Parser for plain text files.

    It converts text into paragraph and list-item blocks.
    Paragraphs are separated by blank lines.
    """

    supported_extensions = SUPPORTED_TEXT_EXTENSIONS

    LIST_PATTERN = re.compile(r"^(?P<indent>\s*)(?P<marker>-|\*|\+|\d+[.)])\s+")

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = self.validate_input_file(file_path)
        content, encoding = self.read_text_with_fallback(
            path,
            failure_code="TEXT_DECODE_FAILED",
        )

        lines = content.splitlines()
        blocks = self._parse_lines(lines)

        return self.build_document(
            path=path,
            file_type=SupportedFileType.TXT,
            blocks=blocks,
            metadata={
                "encoding": encoding,
                "encoding_strategy": "configured text encoding fallback",
            },
        )

    def _parse_lines(self, lines: list[str]) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        paragraph_buffer: list[str] = []
        paragraph_start_line: int | None = None

        def flush_paragraph(end_line: int) -> None:
            nonlocal paragraph_buffer, paragraph_start_line

            if not paragraph_buffer:
                return

            text = " ".join(line.strip() for line in paragraph_buffer).strip()

            if text:
                blocks.append(
                    DocumentBlock(
                        block_type=BlockType.PARAGRAPH,
                        text=text,
                        order=len(blocks),
                        source_location=SourceLocation(
                            line_start=paragraph_start_line,
                            line_end=end_line,
                        ),
                    )
                )

            paragraph_buffer = []
            paragraph_start_line = None

        for index, line in enumerate(lines, start=1):
            stripped = line.strip()

            if not stripped:
                flush_paragraph(index - 1)
                continue

            list_match = self.LIST_PATTERN.match(line)

            if list_match:
                flush_paragraph(index - 1)

                cleaned_text = self.LIST_PATTERN.sub("", line, count=1).strip()

                if cleaned_text:
                    blocks.append(
                        DocumentBlock(
                            block_type=BlockType.LIST_ITEM,
                            text=cleaned_text,
                            order=len(blocks),
                            source_location=SourceLocation(
                                line_start=index,
                                line_end=index,
                            ),
                            metadata={
                                "indent": len(list_match.group("indent")),
                                "marker": list_match.group("marker"),
                                "raw_line": stripped,
                            },
                        )
                    )

                continue

            if paragraph_start_line is None:
                paragraph_start_line = index

            paragraph_buffer.append(line)

        flush_paragraph(len(lines))

        return blocks
