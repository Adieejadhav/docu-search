from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from time import perf_counter

from app.core.exceptions import AppError, UnsupportedFileTypeError
from app.core.observability import (
    DEFAULT_OPERATION_METRICS_RECORDER,
    OperationMetricsRecorder,
)
from app.ingestion.normalizers.block_schema import ParsedDocument
from app.ingestion.parsers.base import BaseDocumentParser
from app.ingestion.parsers.csv_parser import CsvParser
from app.ingestion.parsers.docx_parser import DocxParser
from app.ingestion.parsers.json_parser import JsonParser
from app.ingestion.parsers.markdown_parser import MarkdownParser
from app.ingestion.parsers.pdf_parser import PdfParser
from app.ingestion.parsers.pptx_parser import PptxParser
from app.ingestion.parsers.text_parser import TextParser
from app.ingestion.parsers.xlsx_parser import XlsxParser

DEFAULT_PARSERS: tuple[BaseDocumentParser, ...] = (
    TextParser(),
    MarkdownParser(),
    PdfParser(),
    DocxParser(),
    PptxParser(),
    XlsxParser(),
    CsvParser(),
    JsonParser(),
)


class ParserFactory:
    """
    Selects the correct document parser for a source file.

    The factory owns parser registration and extension lookup so package
    imports do not need to contain parser-selection rules.
    """

    def __init__(
        self,
        parsers: Iterable[BaseDocumentParser] = DEFAULT_PARSERS,
        *,
        metrics_recorder: OperationMetricsRecorder = DEFAULT_OPERATION_METRICS_RECORDER,
        logger: logging.Logger | None = None,
    ) -> None:
        self._parsers = tuple(parsers)
        self._metrics_recorder = metrics_recorder
        self._logger = logger or logging.getLogger(__name__)

        if not self._parsers:
            raise ValueError("ParserFactory requires at least one parser")

        self._parser_by_extension = self._build_parser_index(self._parsers)

    @property
    def parsers(self) -> tuple[BaseDocumentParser, ...]:
        return self._parsers

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset(self._parser_by_extension)

    @property
    def metrics_recorder(self) -> OperationMetricsRecorder:
        return self._metrics_recorder

    def get_parser_for_file(self, file_path: str | Path) -> BaseDocumentParser:
        extension = Path(file_path).suffix.lower()
        parser = self._parser_by_extension.get(extension)

        if parser is None:
            raise UnsupportedFileTypeError(
                f"No parser registered for file type: {extension or '<none>'}",
                code="UNSUPPORTED_FILE_TYPE",
                details={
                    "extension": extension,
                    "supported_extensions": sorted(self.supported_extensions),
                },
            )

        return parser

    def parse_document(self, file_path: str | Path) -> ParsedDocument:
        path = Path(file_path)
        extension = path.suffix.lower()
        parser: BaseDocumentParser | None = None
        start_time = perf_counter()

        try:
            parser = self.get_parser_for_file(path)
            document = parser.parse(path)
        except Exception as exc:
            duration_ms = self._duration_ms(start_time)
            parser_name = self._parser_name(parser)
            error_code = (
                exc.code if isinstance(exc, AppError) else exc.__class__.__name__
            )

            self._metrics_recorder.record_failure(
                operation_name=parser_name,
                error_code=error_code,
                duration_ms=duration_ms,
            )
            self._logger.warning(
                "document_parse_failed",
                extra={
                    "parse_parser": parser_name,
                    "parse_extension": extension,
                    "parse_duration_ms": duration_ms,
                    "parse_error_code": error_code,
                    "parse_file_name": path.name,
                },
                exc_info=True,
            )
            raise

        duration_ms = self._duration_ms(start_time)
        parser_name = self._parser_name(parser)
        self._metrics_recorder.record_success(
            operation_name=parser_name,
            duration_ms=duration_ms,
        )
        self._logger.info(
            "document_parse_succeeded",
            extra={
                "parse_parser": parser_name,
                "parse_extension": extension,
                "parse_duration_ms": duration_ms,
                "parse_block_count": len(document.blocks),
                "parse_file_name": path.name,
            },
        )

        metadata = {
            **document.metadata,
            "parse_duration_ms": duration_ms,
            "block_count": len(document.blocks),
        }
        return document.model_copy(update={"metadata": metadata})

    def _build_parser_index(
        self,
        parsers: tuple[BaseDocumentParser, ...],
    ) -> dict[str, BaseDocumentParser]:
        parser_by_extension: dict[str, BaseDocumentParser] = {}

        for parser in parsers:
            if not parser.supported_extensions:
                raise ValueError(
                    f"{parser.__class__.__name__} must define supported_extensions"
                )

            for extension in parser.supported_extensions:
                normalized_extension = self._normalize_extension(extension)

                if normalized_extension in parser_by_extension:
                    existing_parser = parser_by_extension[normalized_extension]
                    raise ValueError(
                        "Duplicate parser extension registered: "
                        f"{normalized_extension} for "
                        f"{existing_parser.__class__.__name__} and "
                        f"{parser.__class__.__name__}"
                    )

                parser_by_extension[normalized_extension] = parser

        return parser_by_extension

    def _normalize_extension(self, extension: str) -> str:
        cleaned_extension = extension.strip().lower()

        if not cleaned_extension:
            raise ValueError("Parser extension cannot be empty")

        if not cleaned_extension.startswith("."):
            return f".{cleaned_extension}"

        return cleaned_extension

    def _duration_ms(self, start_time: float) -> float:
        return round((perf_counter() - start_time) * 1000, 3)

    def _parser_name(self, parser: BaseDocumentParser | None) -> str:
        if parser is None:
            return "unregistered"

        return parser.__class__.__name__


DEFAULT_PARSER_FACTORY = ParserFactory()


def get_parser_for_file(file_path: str | Path) -> BaseDocumentParser:
    return DEFAULT_PARSER_FACTORY.get_parser_for_file(file_path)


def parse_document(file_path: str | Path) -> ParsedDocument:
    return DEFAULT_PARSER_FACTORY.parse_document(file_path)
