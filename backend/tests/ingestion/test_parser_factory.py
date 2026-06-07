from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.core.exceptions import UnsupportedFileTypeError
from app.core.observability import OperationMetricsRecorder
from app.ingestion.normalizers.block_schema import ParsedDocument
from app.ingestion.parsers.base import BaseDocumentParser
from app.ingestion.parsers.factory import ParserFactory
from app.ingestion.parsers.json_parser import JsonParser
from app.ingestion.parsers.text_parser import TextParser


class DuplicateTextParser(BaseDocumentParser):
    supported_extensions = {".txt"}

    def parse(self, file_path: str | Path) -> ParsedDocument:
        raise NotImplementedError


def test_parser_factory_rejects_duplicate_extensions():
    with pytest.raises(ValueError, match="Duplicate parser extension"):
        ParserFactory([TextParser(), DuplicateTextParser()])


def test_parser_factory_reports_supported_extensions_for_unknown_file():
    factory = ParserFactory([TextParser()])

    with pytest.raises(UnsupportedFileTypeError) as error:
        factory.get_parser_for_file("notes.md")

    assert error.value.code == "UNSUPPORTED_FILE_TYPE"
    assert error.value.details["supported_extensions"] == [".txt"]


def test_parser_factory_records_success_metrics_and_logs(tmp_path, caplog):
    file_path = tmp_path / "document.json"
    file_path.write_text('{"status": "ok"}', encoding="utf-8")
    metrics_recorder = OperationMetricsRecorder()
    factory = ParserFactory([JsonParser()], metrics_recorder=metrics_recorder)

    caplog.set_level(logging.INFO, logger="app.ingestion.parsers.factory")

    document = factory.parse_document(file_path)
    snapshot = metrics_recorder.snapshot()

    assert document.metadata["parse_duration_ms"] >= 0
    assert document.metadata["block_count"] == 1
    assert snapshot.total_count == 1
    assert snapshot.success_count == 1
    assert snapshot.failure_count == 0
    assert snapshot.success_by_operation == {"JsonParser": 1}
    assert any(record.message == "document_parse_succeeded" for record in caplog.records)


def test_parser_factory_records_failure_metrics_and_logs(caplog):
    metrics_recorder = OperationMetricsRecorder()
    factory = ParserFactory([JsonParser()], metrics_recorder=metrics_recorder)

    caplog.set_level(logging.WARNING, logger="app.ingestion.parsers.factory")

    with pytest.raises(UnsupportedFileTypeError):
        factory.parse_document("document.exe")

    snapshot = metrics_recorder.snapshot()

    assert snapshot.total_count == 1
    assert snapshot.success_count == 0
    assert snapshot.failure_count == 1
    assert snapshot.failure_by_operation == {"unregistered": 1}
    assert snapshot.failure_by_code == {"UNSUPPORTED_FILE_TYPE": 1}
    assert any(record.message == "document_parse_failed" for record in caplog.records)
