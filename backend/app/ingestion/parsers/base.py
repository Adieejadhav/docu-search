"""
File: backend/app/ingestion/parsers/base.py
Purpose: Defines the abstract parser contract that all document parsers must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

from app.core.constants import DEFAULT_TEXT_ENCODINGS, SupportedFileType
from app.core.exceptions import (
    EmptyDocumentError,
    FileValidationError,
    ParserError,
    UnsupportedFileTypeError,
)
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument
from app.ingestion.normalizers.pipeline import normalize_document
from app.ingestion.validators.block_validator import validate_parsed_document
from app.ingestion.validators.file_validator import validate_local_file


class BaseDocumentParser(ABC):
    """
    Base contract for all document parsers.

    Every parser must:
    1. Declare supported extensions.
    2. Validate the source file before reading it.
    3. Convert source file into ParsedDocument.
    4. Preserve structure as much as the format exposes.
    """

    supported_extensions: ClassVar[set[str]] = set()

    def can_parse(self, file_path: str | Path) -> bool:
        path = Path(file_path)
        return path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def parse(self, file_path: str | Path) -> ParsedDocument:
        raise NotImplementedError

    def validate_input_file(self, file_path: str | Path) -> Path:
        try:
            validated_file = validate_local_file(
                file_path,
                supported_extensions=self.supported_extensions,
            )
        except FileValidationError as exc:
            if exc.code == "UNSUPPORTED_FILE_TYPE":
                raise UnsupportedFileTypeError(
                    exc.message,
                    code=exc.code,
                    details=exc.details,
                ) from exc

            raise ParserError(
                exc.message,
                code=exc.code,
                details=exc.details,
            ) from exc

        return validated_file.file_path

    def validate_file_exists(self, file_path: str | Path) -> Path:
        return self.validate_input_file(file_path)

    def build_document(
        self,
        *,
        path: Path,
        file_type: SupportedFileType,
        blocks: list[DocumentBlock],
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ParsedDocument:
        if not blocks:
            raise EmptyDocumentError(
                f"No readable content found in file: {path}",
                code="EMPTY_DOCUMENT",
                details={"file_path": str(path)},
            )

        document = ParsedDocument(
            title=title or self.get_document_title(path),
            file_name=self.get_file_name(path),
            file_type=file_type,
            source_path=str(path),
            blocks=blocks,
            metadata={
                "parser": self.__class__.__name__,
                **(metadata or {}),
            },
        )

        return validate_parsed_document(normalize_document(document))

    def read_text_with_fallback(
        self,
        path: Path,
        *,
        failure_code: str,
        read_failure_code: str = "FILE_READ_FAILED",
    ) -> tuple[str, str]:
        for encoding in DEFAULT_TEXT_ENCODINGS:
            try:
                return path.read_text(encoding=encoding).lstrip("\ufeff"), encoding
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                raise ParserError(
                    f"Unable to read file: {path}",
                    code=read_failure_code,
                    details={"file_path": str(path)},
                ) from exc

        raise ParserError(
            f"Unable to decode text file: {path}",
            code=failure_code,
            details={"file_path": str(path), "encodings": DEFAULT_TEXT_ENCODINGS},
        )

    def get_document_title(self, file_path: str | Path) -> str:
        return Path(file_path).stem.strip() or "Untitled Document"

    def get_file_name(self, file_path: str | Path) -> str:
        return Path(file_path).name
