from __future__ import annotations

from pathlib import Path

import pytest

from app.core.constants import BlockType, SupportedFileType
from app.core.exceptions import IngestionError, ParserError
from app.indexing import PgVectorIndexStats
from app.ingestion.chunking import ParentChildChunkingConfig, create_chunker
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)
from app.ingestion.orchestrator import IngestionOrchestrator, resolve_input_paths


def test_ingestion_orchestrator_parses_chunks_and_indexes_files(tmp_path):
    source_file = tmp_path / "policy.txt"
    source_file.write_text("policy body", encoding="utf-8")
    index = _FakeIndex()

    result = IngestionOrchestrator(
        parser_factory=_FakeParserFactory(),
        chunker=create_chunker(
            config=ParentChildChunkingConfig(
                parent_target_tokens=80,
                parent_hard_max_tokens=120,
                child_target_tokens=40,
                child_overlap_tokens=0,
            )
        ),
        index=index,
    ).ingest([source_file], clear_index=True)

    assert result.input_count == 1
    assert result.parsed_document_count == 1
    assert result.chunked_document_count == 1
    assert result.indexed_child_count == result.child_chunk_count
    assert result.failure_count == 0
    assert index.clear_called is True
    assert index.indexed_documents[0].file_name == "policy.txt"


def test_ingestion_orchestrator_can_continue_after_file_failure(tmp_path):
    good_file = tmp_path / "good.txt"
    bad_file = tmp_path / "bad.txt"
    good_file.write_text("ok", encoding="utf-8")
    bad_file.write_text("bad", encoding="utf-8")

    result = IngestionOrchestrator(
        parser_factory=_FakeParserFactory(fail_names={"bad.txt"}),
        index=_FakeIndex(),
    ).ingest([good_file, bad_file], continue_on_error=True)

    assert result.parsed_document_count == 1
    assert result.chunked_document_count == 1
    assert result.failure_count == 1
    assert result.failures[0].code == "TEST_PARSE_FAILED"


def test_ingestion_orchestrator_raises_when_no_supported_files(tmp_path):
    unsupported_file = tmp_path / "image.png"
    unsupported_file.write_text("not supported", encoding="utf-8")

    with pytest.raises(IngestionError) as error:
        IngestionOrchestrator(
            parser_factory=_FakeParserFactory(),
            index=_FakeIndex(),
        ).ingest([unsupported_file])

    assert error.value.code == "NO_INPUT_FILES_FOUND"


def test_resolve_input_paths_skips_office_lock_files(tmp_path):
    source_file = tmp_path / "source.txt"
    lock_file = tmp_path / "~$source.txt"
    source_file.write_text("ok", encoding="utf-8")
    lock_file.write_text("skip", encoding="utf-8")

    paths = list(
        resolve_input_paths(
            [tmp_path],
            recursive=False,
            supported_extensions=frozenset({".txt"}),
        )
    )

    assert paths == [source_file]


class _FakeParserFactory:
    supported_extensions = frozenset({".txt"})

    def __init__(self, *, fail_names: set[str] | None = None) -> None:
        self.fail_names = fail_names or set()

    def parse_document(self, path: str | Path) -> ParsedDocument:
        file_path = Path(path)
        if file_path.name in self.fail_names:
            raise ParserError(
                "test parser failure",
                code="TEST_PARSE_FAILED",
                details={"file_name": file_path.name},
            )

        return ParsedDocument(
            title=file_path.stem,
            file_name=file_path.name,
            file_type=SupportedFileType.TXT,
            source_path=str(file_path),
            blocks=[
                DocumentBlock(
                    block_type=BlockType.HEADING,
                    text=file_path.stem,
                    order=0,
                    level=1,
                    source_location=SourceLocation(line_start=1, line_end=1),
                ),
                DocumentBlock(
                    block_type=BlockType.PARAGRAPH,
                    text="P-004 satellite mode syncs within 14 days.",
                    order=1,
                    parent_path=[file_path.stem],
                    source_location=SourceLocation(line_start=2, line_end=2),
                ),
            ],
            metadata={},
        )


class _FakeIndex:
    def __init__(self) -> None:
        self.clear_called = False
        self.indexed_documents = []

    def clear(self) -> None:
        self.clear_called = True

    def index_documents(self, documents, *, replace: bool = True) -> int:
        self.indexed_documents.extend(documents)
        return sum(len(document.child_chunks) for document in documents)

    def stats(self) -> PgVectorIndexStats:
        return PgVectorIndexStats(
            document_count=len(self.indexed_documents),
            parent_chunk_count=sum(
                len(document.parent_chunks) for document in self.indexed_documents
            ),
            child_chunk_count=sum(
                len(document.child_chunks) for document in self.indexed_documents
            ),
            embedding_model="fake-embedding",
            embedding_dimensions=3,
        )
