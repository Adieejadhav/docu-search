from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader

from app.core.constants import BlockType, SupportedFileType, SUPPORTED_PDF_EXTENSIONS
from app.core.exceptions import ParserError
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)
from app.ingestion.parsers.base import BaseDocumentParser


class PdfParser(BaseDocumentParser):
    """
    Parser for text-based PDF files.

    Scanned/image-only PDFs require OCR and will intentionally surface as empty
    documents instead of pretending unreadable pixels are text.
    """

    supported_extensions = SUPPORTED_PDF_EXTENSIONS

    def parse(self, file_path: str | Path) -> ParsedDocument:
        path = self.validate_input_file(file_path)
        reader = self._open_reader(path)
        blocks = self._parse_pages(reader)
        title = self._extract_title(reader.metadata) or self.get_document_title(path)

        return self.build_document(
            path=path,
            title=title,
            file_type=SupportedFileType.PDF,
            blocks=blocks,
            metadata={
                "page_count": len(reader.pages),
                "encrypted": bool(reader.is_encrypted),
            },
        )

    def _open_reader(self, path: Path) -> PdfReader:
        try:
            reader = PdfReader(str(path))
        except Exception as exc:
            raise ParserError(
                f"Unable to open PDF file: {path}",
                code="PDF_OPEN_FAILED",
                details={"file_path": str(path)},
            ) from exc

        if reader.is_encrypted:
            try:
                decrypt_result = reader.decrypt("")
            except Exception as exc:
                raise ParserError(
                    f"Unable to decrypt PDF file: {path}",
                    code="PDF_ENCRYPTED",
                    details={"file_path": str(path)},
                ) from exc

            if decrypt_result == 0:
                raise ParserError(
                    f"PDF is encrypted and requires a password: {path}",
                    code="PDF_ENCRYPTED",
                    details={"file_path": str(path)},
                )

        return reader

    def _parse_pages(self, reader: PdfReader) -> list[DocumentBlock]:
        blocks: list[DocumentBlock] = []

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise ParserError(
                    "Unable to extract text from PDF page",
                    code="PDF_TEXT_EXTRACTION_FAILED",
                    details={"page_number": page_number},
                ) from exc

            for paragraph in self._split_page_text(page_text):
                blocks.append(
                    DocumentBlock(
                        block_type=BlockType.PARAGRAPH,
                        text=paragraph,
                        order=len(blocks),
                        source_location=SourceLocation(page_number=page_number),
                        metadata={"page_number": page_number},
                    )
                )

        return blocks

    def _split_page_text(self, text: str) -> list[str]:
        paragraphs: list[str] = []
        buffer: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                if buffer:
                    paragraphs.append(" ".join(buffer).strip())
                    buffer = []
                continue

            buffer.append(stripped)

        if buffer:
            paragraphs.append(" ".join(buffer).strip())

        return [paragraph for paragraph in paragraphs if paragraph]

    def _extract_title(self, metadata: Any) -> str | None:
        title = getattr(metadata, "title", None)
        if not isinstance(title, str):
            return None

        title = title.strip()
        return title or None
