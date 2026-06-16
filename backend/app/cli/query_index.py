from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import AppError
from app.core.env import load_environment
from app.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.search.retrieval import RetrievalResult


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    load_environment()
    args = build_parser().parse_args(argv)

    try:
        index = PgVectorChunkIndex(
            database_url=args.database_url,
            embedding_provider=LocalSentenceTransformerEmbeddingProvider(
                model=args.embedding_model,
                dimensions=args.embedding_dimensions,
                device=args.embedding_device,
            ),
        )
        metadata_filters = build_metadata_filters(args)
        result = index.retrieve(
            args.query,
            top_k=args.top_k,
            metadata_filters=metadata_filters,
        )
    except Exception as exc:
        print_error(exc)
        return 1

    if args.output_json is not None:
        write_retrieval_json(result, args.output_json)
        print(f"Wrote retrieval JSON output to: {args.output_json}")

    if args.dump_json:
        print_retrieval_json(result)
    else:
        print_summary(result, show_parent=args.show_parent)

    return 0


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-query",
        description="Query a PostgreSQL + pgvector parent-child retrieval index.",
    )
    parser.add_argument(
        "query",
        help="Search query.",
    )
    parser.add_argument("--database-url", help="PostgreSQL DATABASE_URL.")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of child chunk matches to return.",
    )
    parser.add_argument(
        "--file-name",
        help="Optional exact file_name filter.",
    )
    parser.add_argument(
        "--file-type",
        help="Optional exact file_type filter.",
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
        "--show-parent",
        action="store_true",
        help="Print parent chunk previews after each child hit.",
    )
    parser.add_argument(
        "--dump-json",
        action="store_true",
        help="Print the complete retrieval result JSON.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Write the complete retrieval result JSON to a file.",
    )
    return parser


def build_metadata_filters(args: argparse.Namespace) -> dict[str, Any] | None:
    filters: dict[str, Any] = {}
    if args.file_name:
        filters["file_name"] = args.file_name
    if args.file_type:
        filters["file_type"] = args.file_type

    return filters or None


def write_retrieval_json(result: RetrievalResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_retrieval_json(result: RetrievalResult) -> None:
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


def print_summary(result: RetrievalResult, *, show_parent: bool) -> None:
    print("PERSISTENT RETRIEVAL SUMMARY")
    print(f"  query: {result.query}")
    print(f"  embedding_model: {result.embedding_model}")
    print(f"  database_url: {result.metadata.get('database_url')}")
    print(f"  indexed_child_chunks: {result.metadata.get('indexed_child_chunk_count')}")
    print(f"  returned_results: {len(result.results)}")
    print()

    for item in result.results:
        child = item.child_chunk
        parent = item.parent_chunk
        print("=" * 100)
        print(f"[{item.rank}] score={item.score:.4f}")
        print(f"  file: {item.metadata.get('file_name')}")
        if child.parent_path:
            print(f"  parent_path: {' > '.join(child.parent_path)}")
        if child.source_refs:
            print(f"  source_refs: {', '.join(child.source_refs)}")
        print("  child:")
        print(indent_text(preview_text(child.text), spaces=4))
        if show_parent:
            print("  parent:")
            print(indent_text(preview_text(parent.text, max_length=700), spaces=4))


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
        print("ERROR: INVALID_RETRIEVAL_RESULT", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return

    print(f"ERROR: {exc}", file=sys.stderr)


def preview_text(text: str, *, max_length: int = 400) -> str:
    normalized_text = text.strip()
    if len(normalized_text) <= max_length:
        return normalized_text

    return normalized_text[: max_length - 3].rstrip() + "..."


def indent_text(text: str, *, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines() or [""])


if __name__ == "__main__":
    raise SystemExit(main())
