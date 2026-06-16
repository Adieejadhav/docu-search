from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError as PydanticValidationError

from app.core.env import load_environment
from app.core.exceptions import AppError
from app.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.ingestion import (
    IngestionOrchestrator,
    IngestionPipelineResult,
    IngestionProgressEvent,
)
from app.ingestion.chunking import ParentChildChunkingConfig, create_chunker
from app.ingestion.parsers.factory import ParserFactory


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    load_environment()
    args = build_parser().parse_args(argv)

    try:
        orchestrator = IngestionOrchestrator(
            parser_factory=ParserFactory(),
            chunker=create_chunker(
                config=ParentChildChunkingConfig(
                    parent_target_tokens=args.parent_target_tokens,
                    parent_hard_max_tokens=args.parent_hard_max_tokens,
                    child_target_tokens=args.child_target_tokens,
                    child_overlap_tokens=args.child_overlap_tokens,
                    include_context_prefix=not args.no_context_prefix,
                )
            ),
            index=PgVectorChunkIndex(
                database_url=args.database_url,
                embedding_provider=LocalSentenceTransformerEmbeddingProvider(
                    model=args.embedding_model,
                    dimensions=args.embedding_dimensions,
                    batch_size=args.embedding_batch_size,
                    device=args.embedding_device,
                ),
            ),
        )
        result = orchestrator.ingest(
            args.paths,
            recursive=args.recursive,
            clear_index=args.clear_index,
            replace=not args.no_replace,
            continue_on_error=args.continue_on_error,
            progress_callback=print_progress_event,
        )
    except Exception as exc:
        print_error(exc)
        return 1

    try:
        if args.normalized_output_json is not None:
            write_start = perf_counter()
            print_progress_event(
                IngestionProgressEvent(
                    stage="write",
                    status="started",
                    message=f"Writing normalized JSON to {args.normalized_output_json}",
                )
            )
            write_json(
                [document.model_dump(mode="json") for document in result.parsed_documents],
                args.normalized_output_json,
            )
            print_progress_event(
                IngestionProgressEvent(
                    stage="write",
                    status="completed",
                    message=f"Wrote normalized JSON to {args.normalized_output_json}",
                    duration_ms=duration_ms(write_start),
                )
            )

        if args.chunks_output_json is not None:
            write_start = perf_counter()
            print_progress_event(
                IngestionProgressEvent(
                    stage="write",
                    status="started",
                    message=f"Writing chunk JSON to {args.chunks_output_json}",
                )
            )
            write_json(
                [document.model_dump(mode="json") for document in result.chunked_documents],
                args.chunks_output_json,
            )
            print_progress_event(
                IngestionProgressEvent(
                    stage="write",
                    status="completed",
                    message=f"Wrote chunk JSON to {args.chunks_output_json}",
                    duration_ms=duration_ms(write_start),
                )
            )
    except Exception as exc:
        print_error(exc)
        return 1

    print_summary(result)
    return 1 if result.failures else 0


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-ingest",
        description=(
            "Parse, normalize, chunk, embed, and index source documents into "
            "PostgreSQL + pgvector."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files, directories, or glob patterns to ingest.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan directory inputs and recursive glob patterns.",
    )
    parser.add_argument("--database-url", help="PostgreSQL DATABASE_URL.")
    parser.add_argument(
        "--clear-index",
        action="store_true",
        help="Clear the pgvector index before inserting successfully chunked documents.",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Do not delete matching document IDs before upsert.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue indexing other files when one file fails parsing or chunking.",
    )
    parser.add_argument(
        "--normalized-output-json",
        type=Path,
        help="Write parsed/normalized documents to JSON for inspection.",
    )
    parser.add_argument(
        "--chunks-output-json",
        type=Path,
        help="Write chunked documents to JSON for inspection.",
    )
    parser.add_argument(
        "--parent-target-tokens",
        type=int,
        default=1200,
        help="Approximate target token count for parent chunks.",
    )
    parser.add_argument(
        "--parent-hard-max-tokens",
        type=int,
        default=2000,
        help="Approximate hard maximum token count before splitting one source block.",
    )
    parser.add_argument(
        "--child-target-tokens",
        type=int,
        default=350,
        help="Approximate target token count for child chunks.",
    )
    parser.add_argument(
        "--child-overlap-tokens",
        type=int,
        default=60,
        help="Approximate overlap between child chunks.",
    )
    parser.add_argument(
        "--no-context-prefix",
        action="store_true",
        help="Do not prepend document and section context to chunk text.",
    )
    parser.add_argument(
        "--embedding-model",
        default=os.getenv(
            "LOCAL_EMBEDDING_MODEL",
            LocalSentenceTransformerEmbeddingProvider.DEFAULT_MODEL,
        ),
        help="Local sentence-transformers embedding model.",
    )
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=int(
            os.getenv(
                "LOCAL_EMBEDDING_DIMENSIONS",
                str(LocalSentenceTransformerEmbeddingProvider.DEFAULT_DIMENSIONS),
            )
        ),
        help="Embedding dimensions. Must match the pgvector index.",
    )
    parser.add_argument(
        "--embedding-device",
        default=os.getenv("LOCAL_EMBEDDING_DEVICE"),
        help="Optional sentence-transformers device, for example cpu, cuda, or mps.",
    )
    parser.add_argument(
        "--embedding-batch-size",
        type=int,
        default=int(
            os.getenv(
                "LOCAL_EMBEDDING_BATCH_SIZE",
                str(LocalSentenceTransformerEmbeddingProvider.DEFAULT_BATCH_SIZE),
            )
        ),
        help="Local embedding batch size.",
    )
    return parser


def write_json(payload: object, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_progress_event(event: IngestionProgressEvent) -> None:
    stage = event.stage.replace("_", " ").upper()
    status = {
        "started": "START",
        "completed": "DONE",
        "failed": "FAILED",
    }.get(event.status, event.status.upper())
    duration = (
        f" in {format_duration_ms(event.duration_ms)}"
        if event.duration_ms is not None
        else ""
    )
    details = format_progress_details(event.metadata)
    print(
        f"[{stage} {status}] {event.message}{duration}{details}",
        flush=True,
    )


def format_progress_details(metadata: dict[str, object]) -> str:
    detail_keys = (
        "block_count",
        "parser",
        "parent_chunks",
        "child_chunks",
        "indexed_child_chunks",
    )
    details = [
        f"{key}={metadata[key]}"
        for key in detail_keys
        if metadata.get(key) is not None
    ]
    return f" ({', '.join(details)})" if details else ""


def duration_ms(start_time: float) -> float:
    return round((perf_counter() - start_time) * 1000, 3)


def format_duration_ms(value: float) -> str:
    if value >= 1000:
        return f"{value / 1000:.2f}s"
    return f"{value:.1f}ms"


def print_summary(result: IngestionPipelineResult) -> None:
    print("INGESTION SUMMARY")
    print(f"  discovered_input_files: {result.input_count}")
    print(f"  parsed_documents: {result.parsed_document_count}")
    print(f"  chunked_documents: {result.chunked_document_count}")
    print(f"  parent_chunks_created: {result.parent_chunk_count}")
    print(f"  child_chunks_created: {result.child_chunk_count}")
    print(f"  indexed_child_chunks: {result.indexed_child_count}")
    if result.index_stats is not None:
        print(f"  total_documents_in_index: {result.index_stats.document_count}")
        print(f"  total_parent_chunks_in_index: {result.index_stats.parent_chunk_count}")
        print(f"  total_child_chunks_in_index: {result.index_stats.child_chunk_count}")
        print(f"  embedding_model: {result.index_stats.embedding_model}")
        print(f"  embedding_dimensions: {result.index_stats.embedding_dimensions}")
    print(f"  failures: {result.failure_count}")
    if result.timings_ms:
        print("  timings:")
        for key in (
            "discover",
            "parse",
            "chunk",
            "index_clear",
            "index",
            "stats",
            "total",
        ):
            if key in result.timings_ms:
                print(f"    {key}: {format_duration_ms(result.timings_ms[key])}")

    if result.failures:
        print()
        print("FAILURES")
        for failure in result.failures:
            print(f"  - {failure.path}: {failure.code}: {failure.message}")


def print_error(exc: Exception) -> None:
    if isinstance(exc, AppError):
        print(f"ERROR: {exc.code}: {exc.message}", file=sys.stderr)
        if exc.details:
            print("DETAILS:", file=sys.stderr)
            print(
                json.dumps(exc.details, indent=2, sort_keys=True, default=str),
                file=sys.stderr,
            )
        return

    if isinstance(exc, PydanticValidationError):
        print("ERROR: INVALID_INGESTION_RESULT", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return

    print(f"ERROR: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
