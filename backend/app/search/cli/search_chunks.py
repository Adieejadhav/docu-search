from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import AppError
from app.ingestion.chunking import ChunkedDocument
from app.search.embeddings import HashEmbeddingProvider
from app.search.retrieval import ParentChildRetriever, RetrievalResult


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    args = build_parser().parse_args(argv)

    try:
        documents = read_chunked_documents(args.input_json)
        retriever = ParentChildRetriever(
            embedding_provider=HashEmbeddingProvider(
                dimensions=args.embedding_dimensions
            )
        )
        indexed_count = retriever.index_documents(documents)
        metadata_filters = build_metadata_filters(args)
        result = retriever.retrieve(
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
        print_summary(
            result,
            indexed_count=indexed_count,
            show_parent=args.show_parent,
        )

    return 0


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-retrieve",
        description="Run local parent-child retrieval over chunk JSON.",
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="ChunkedDocument JSON file produced by docu-chunk --output-json.",
    )
    parser.add_argument("query", help="Search query.")
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
        "--embedding-dimensions",
        type=int,
        default=384,
        help="Dimensions for the local hash embedding provider.",
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


def read_chunked_documents(input_path: Path) -> list[ChunkedDocument]:
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Unable to read input JSON file: {input_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {input_path}: line {exc.lineno}, column {exc.colno}"
        ) from exc

    if isinstance(payload, list):
        if not payload:
            raise ValueError("input JSON must contain at least one chunked document")
        return [ChunkedDocument.model_validate(item) for item in payload]

    if isinstance(payload, dict):
        return [ChunkedDocument.model_validate(payload)]

    raise ValueError("input JSON must be a ChunkedDocument object or list")


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


def print_summary(
    result: RetrievalResult,
    *,
    indexed_count: int,
    show_parent: bool,
) -> None:
    print("RETRIEVAL SUMMARY")
    print(f"  query: {result.query}")
    print(f"  embedding_model: {result.embedding_model}")
    print(f"  indexed_child_chunks: {indexed_count}")
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
        print("ERROR: INVALID_CHUNKED_DOCUMENT", file=sys.stderr)
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
