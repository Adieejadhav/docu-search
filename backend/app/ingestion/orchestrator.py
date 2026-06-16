"""
File: backend/app/ingestion/orchestrator.py
Purpose: Orchestrates parse, chunk, embed, and pgvector indexing for source files.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
import glob
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any, Protocol

from app.core.exceptions import AppError, IngestionError
from app.ingestion.chunking import ChunkedDocument, StructureAwareParentChildChunker
from app.ingestion.chunking.factory import create_chunker
from app.ingestion.normalizers.block_schema import ParsedDocument
from app.ingestion.parsers.factory import ParserFactory
from app.ingestion.validators.file_validator import should_skip_ingestion_file

if TYPE_CHECKING:
    from app.indexing.pgvector_index import PgVectorChunkIndex, PgVectorIndexStats


class ChunkIndex(Protocol):
    def clear(self) -> None: ...

    def index_documents(
        self,
        documents: list[ChunkedDocument],
        *,
        replace: bool = True,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> int: ...

    def stats(self) -> "PgVectorIndexStats": ...


@dataclass(frozen=True)
class IngestionProgressEvent:
    stage: str
    status: str
    message: str
    path: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[IngestionProgressEvent], None]


@dataclass(frozen=True)
class IngestionFailure:
    path: str
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestionPipelineResult:
    input_count: int
    parsed_documents: list[ParsedDocument]
    chunked_documents: list[ChunkedDocument]
    indexed_child_count: int
    index_stats: "PgVectorIndexStats | None"
    failures: list[IngestionFailure] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)

    @property
    def parsed_document_count(self) -> int:
        return len(self.parsed_documents)

    @property
    def chunked_document_count(self) -> int:
        return len(self.chunked_documents)

    @property
    def parent_chunk_count(self) -> int:
        return sum(len(document.parent_chunks) for document in self.chunked_documents)

    @property
    def child_chunk_count(self) -> int:
        return sum(len(document.child_chunks) for document in self.chunked_documents)

    @property
    def failure_count(self) -> int:
        return len(self.failures)


class IngestionOrchestrator:
    """
    Runs the end-to-end document ingestion/indexing pipeline.
    """

    def __init__(
        self,
        *,
        parser_factory: ParserFactory | None = None,
        chunker: StructureAwareParentChildChunker | None = None,
        index: "PgVectorChunkIndex | ChunkIndex | None" = None,
    ) -> None:
        self.parser_factory = parser_factory or ParserFactory()
        self.chunker = chunker or create_chunker()
        if index is None:
            from app.indexing.pgvector_index import PgVectorChunkIndex

            self.index: ChunkIndex = PgVectorChunkIndex()
        else:
            self.index = index

    def ingest(
        self,
        inputs: Iterable[str | Path],
        *,
        recursive: bool = False,
        clear_index: bool = False,
        replace: bool = True,
        continue_on_error: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> IngestionPipelineResult:
        total_start = perf_counter()
        timings_ms: dict[str, float] = {}
        discovery_start = perf_counter()
        _emit_progress(
            progress_callback,
            stage="discover",
            status="started",
            message="Discovering supported input files",
        )
        paths = list(
            resolve_input_paths(
                inputs,
                recursive=recursive,
                supported_extensions=self.parser_factory.supported_extensions,
            )
        )
        discovery_ms = _duration_ms(discovery_start)
        timings_ms["discover"] = discovery_ms
        _emit_progress(
            progress_callback,
            stage="discover",
            status="completed",
            message=f"Discovered {len(paths)} supported input files",
            duration_ms=discovery_ms,
        )

        if not paths:
            raise IngestionError(
                "No supported input files found",
                code="NO_INPUT_FILES_FOUND",
                details={
                    "supported_extensions": sorted(self.parser_factory.supported_extensions),
                },
            )

        failures: list[IngestionFailure] = []
        parsed_documents: list[ParsedDocument] = []
        chunked_documents: list[ChunkedDocument] = []

        for file_index, path in enumerate(paths, start=1):
            file_metadata = {
                "file_index": file_index,
                "file_count": len(paths),
                "file_name": path.name,
            }
            try:
                parse_start = perf_counter()
                _emit_progress(
                    progress_callback,
                    stage="parse",
                    status="started",
                    message=f"Parsing {path.name} ({file_index}/{len(paths)})",
                    path=str(path),
                    metadata=file_metadata,
                )
                parsed_document = self.parser_factory.parse_document(path)
                parse_ms = _duration_ms(parse_start)
                timings_ms["parse"] = timings_ms.get("parse", 0.0) + parse_ms
                _emit_progress(
                    progress_callback,
                    stage="parse",
                    status="completed",
                    message=f"Parsed {path.name}",
                    path=str(path),
                    duration_ms=parse_ms,
                    metadata={
                        **file_metadata,
                        "block_count": len(parsed_document.blocks),
                        "parser": parsed_document.metadata.get("parser"),
                    },
                )

                chunk_start = perf_counter()
                _emit_progress(
                    progress_callback,
                    stage="chunk",
                    status="started",
                    message=f"Chunking {path.name} ({file_index}/{len(paths)})",
                    path=str(path),
                    metadata=file_metadata,
                )
                chunked_document = self.chunker.chunk(parsed_document)
                chunk_ms = _duration_ms(chunk_start)
                timings_ms["chunk"] = timings_ms.get("chunk", 0.0) + chunk_ms
                _emit_progress(
                    progress_callback,
                    stage="chunk",
                    status="completed",
                    message=f"Chunked {path.name}",
                    path=str(path),
                    duration_ms=chunk_ms,
                    metadata={
                        **file_metadata,
                        "parent_chunks": len(chunked_document.parent_chunks),
                        "child_chunks": len(chunked_document.child_chunks),
                    },
                )
            except Exception as exc:
                failure = self._failure_from_exception(path=path, exc=exc)
                failures.append(failure)
                _emit_progress(
                    progress_callback,
                    stage="file",
                    status="failed",
                    message=f"Failed {path.name}: {failure.code}",
                    path=str(path),
                    metadata={**file_metadata, **failure.details},
                )
                if not continue_on_error:
                    raise IngestionError(
                        "Ingestion failed for input file",
                        code=failure.code,
                        details={
                            "path": failure.path,
                            "message": failure.message,
                            **failure.details,
                        },
                    ) from exc
                continue

            parsed_documents.append(parsed_document)
            chunked_documents.append(chunked_document)

        indexed_child_count = 0
        index_stats: PgVectorIndexStats | None = None
        if chunked_documents:
            if clear_index:
                clear_start = perf_counter()
                _emit_progress(
                    progress_callback,
                    stage="index_clear",
                    status="started",
                    message="Clearing existing pgvector index data",
                )
                self.index.clear()
                clear_ms = _duration_ms(clear_start)
                timings_ms["index_clear"] = clear_ms
                _emit_progress(
                    progress_callback,
                    stage="index_clear",
                    status="completed",
                    message="Cleared existing pgvector index data",
                    duration_ms=clear_ms,
                )

            index_start = perf_counter()
            _emit_progress(
                progress_callback,
                stage="index",
                status="started",
                message=(
                    f"Embedding and indexing {len(chunked_documents)} documents "
                    f"with {self._child_chunk_count(chunked_documents)} child chunks"
                ),
            )
            index_progress_callback = (
                self._index_progress_callback(progress_callback, len(chunked_documents))
                if progress_callback is not None
                else None
            )
            if index_progress_callback is None:
                indexed_child_count = self.index.index_documents(
                    chunked_documents,
                    replace=replace,
                )
            else:
                indexed_child_count = self.index.index_documents(
                    chunked_documents,
                    replace=replace,
                    progress_callback=index_progress_callback,
                )
            index_ms = _duration_ms(index_start)
            timings_ms["index"] = index_ms
            _emit_progress(
                progress_callback,
                stage="index",
                status="completed",
                message=f"Indexed {indexed_child_count} child chunks",
                duration_ms=index_ms,
            )

            stats_start = perf_counter()
            _emit_progress(
                progress_callback,
                stage="stats",
                status="started",
                message="Reading pgvector index stats",
            )
            index_stats = self.index.stats()
            stats_ms = _duration_ms(stats_start)
            timings_ms["stats"] = stats_ms
            _emit_progress(
                progress_callback,
                stage="stats",
                status="completed",
                message="Read pgvector index stats",
                duration_ms=stats_ms,
            )

        total_ms = _duration_ms(total_start)
        timings_ms["total"] = total_ms
        _emit_progress(
            progress_callback,
            stage="ingest",
            status="completed",
            message="Ingestion pipeline completed",
            duration_ms=total_ms,
        )

        return IngestionPipelineResult(
            input_count=len(paths),
            parsed_documents=parsed_documents,
            chunked_documents=chunked_documents,
            indexed_child_count=indexed_child_count,
            index_stats=index_stats,
            failures=failures,
            timings_ms=timings_ms,
        )

    def _index_progress_callback(
        self,
        progress_callback: ProgressCallback,
        document_count: int,
    ) -> Callable[[dict[str, Any]], None]:
        def callback(event: dict[str, Any]) -> None:
            document = event.get("document")
            file_name = getattr(document, "file_name", "unknown document")
            file_index = int(event.get("document_index", 0))
            metadata = {
                "file_index": file_index,
                "file_count": document_count,
                "file_name": file_name,
                "child_chunks": event.get("child_chunks"),
            }
            if event.get("status") == "started":
                _emit_progress(
                    progress_callback,
                    stage="index_document",
                    status="started",
                    message=(
                        f"Embedding and indexing {file_name} "
                        f"({file_index}/{document_count})"
                    ),
                    metadata=metadata,
                )
                return

            _emit_progress(
                progress_callback,
                stage="index_document",
                status="completed",
                message=f"Indexed {file_name}",
                duration_ms=event.get("duration_ms"),
                metadata={
                    **metadata,
                    "indexed_child_chunks": event.get("indexed_child_chunks"),
                },
            )

        return callback

    def _child_chunk_count(self, documents: list[ChunkedDocument]) -> int:
        return sum(len(document.child_chunks) for document in documents)

    def _failure_from_exception(self, *, path: Path, exc: Exception) -> IngestionFailure:
        if isinstance(exc, AppError):
            return IngestionFailure(
                path=str(path),
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )

        return IngestionFailure(
            path=str(path),
            code=exc.__class__.__name__,
            message=str(exc),
        )


def resolve_input_paths(
    inputs: Iterable[str | Path],
    *,
    recursive: bool,
    supported_extensions: frozenset[str],
) -> Iterable[Path]:
    seen_paths: set[Path] = set()

    for raw_input in inputs:
        matches = expand_input(raw_input, recursive=recursive)

        for path in matches:
            if path.is_dir():
                yield from iter_directory_files(
                    path,
                    recursive=recursive,
                    supported_extensions=supported_extensions,
                    seen_paths=seen_paths,
                )
                continue

            resolved_path = path.resolve()
            if (
                resolved_path in seen_paths
                or not path.is_file()
                or should_skip_ingestion_file(path)
                or path.suffix.lower() not in supported_extensions
            ):
                continue

            seen_paths.add(resolved_path)
            yield path


def expand_input(raw_input: str | Path, *, recursive: bool) -> list[Path]:
    raw_value = str(raw_input)
    if has_glob_pattern(raw_value):
        matches = glob.glob(raw_value, recursive=recursive)
        return [Path(match) for match in sorted(matches)]

    return [Path(raw_input)]


def has_glob_pattern(value: str) -> bool:
    return any(character in value for character in "*?[]")


def iter_directory_files(
    directory: Path,
    *,
    recursive: bool,
    supported_extensions: frozenset[str],
    seen_paths: set[Path],
) -> Iterable[Path]:
    iterator = directory.rglob("*") if recursive else directory.iterdir()

    for path in sorted(iterator):
        if (
            not path.is_file()
            or should_skip_ingestion_file(path)
            or path.suffix.lower() not in supported_extensions
        ):
            continue

        resolved_path = path.resolve()
        if resolved_path in seen_paths:
            continue

        seen_paths.add(resolved_path)
        yield path


def _duration_ms(start_time: float) -> float:
    return round((perf_counter() - start_time) * 1000, 3)


def _emit_progress(
    callback: ProgressCallback | None,
    *,
    stage: str,
    status: str,
    message: str,
    path: str | None = None,
    duration_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return

    callback(
        IngestionProgressEvent(
            stage=stage,
            status=status,
            message=message,
            path=path,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
    )
