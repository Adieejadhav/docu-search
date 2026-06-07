from __future__ import annotations

import csv
import io
from pathlib import Path

from app.core.constants import BlockType, SupportedFileType, SUPPORTED_CSV_EXTENSIONS
from app.core.exceptions import ParserError
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)
from app.ingestion.parsers._tabular import (
    dedupe_headers,
    format_key_value_row,
    normalize_row,
    row_is_empty,
)
from app.ingestion.parsers.base import BaseDocumentParser


class CsvParser(BaseDocumentParser):
    """
    Parser for comma-separated value files.

    The first non-empty row is treated as the header row. Each following
    non-empty row becomes one table block with key-value text for retrieval.
    """

    supported_extensions = SUPPORTED_CSV_EXTENSIONS

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = self.validate_input_file(file_path)
        content, encoding = self.read_text_with_fallback(
            path,
            failure_code="CSV_DECODE_FAILED",
        )
        blocks = self._parse_csv(content)

        return self.build_document(
            path=path,
            file_type=SupportedFileType.CSV,
            blocks=blocks,
            metadata={
                "encoding": encoding,
                "encoding_strategy": "configured text encoding fallback",
                "delimiter": ",",
            },
        )

    def _parse_csv(self, content: str) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []
        reader = csv.reader(io.StringIO(content), delimiter=",")
        headers: list[str] | None = None
        header_line_number: int | None = None

        try:
            for line_number, row in enumerate(reader, start=1):
                normalized_row = normalize_row(row)

                if row_is_empty(normalized_row):
                    continue

                if headers is None:
                    headers = dedupe_headers(normalized_row)
                    header_line_number = line_number
                    continue

                text = format_key_value_row(headers, normalized_row)
                if not text:
                    continue

                blocks.append(
                    DocumentBlock(
                        block_type=BlockType.TABLE,
                        text=text,
                        order=len(blocks),
                        source_location=SourceLocation(
                            line_start=line_number,
                            line_end=line_number,
                        ),
                        metadata={
                            "format": "csv_row",
                            "header_line": header_line_number,
                            "row_number": line_number,
                            "columns": headers,
                        },
                    )
                )
        except csv.Error as exc:
            raise ParserError(
                "Unable to parse CSV file",
                code="CSV_PARSE_FAILED",
                details={"reason": str(exc)},
            ) from exc

        if headers is not None and not blocks:
            blocks.append(
                DocumentBlock(
                    block_type=BlockType.TABLE,
                    text="Columns: " + " | ".join(headers),
                    order=0,
                    source_location=SourceLocation(
                        line_start=header_line_number,
                        line_end=header_line_number,
                    ),
                    metadata={
                        "format": "csv_header",
                        "header_line": header_line_number,
                        "columns": headers,
                    },
                )
            )

        return blocks
