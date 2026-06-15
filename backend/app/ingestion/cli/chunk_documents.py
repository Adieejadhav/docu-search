from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import AppError
from app.ingestion.chunking import (
    ChunkedDocument,
    ParentChildChunkingConfig,
    create_chunker,
)
from app.ingestion.normalizers.block_schema import ParsedDocument


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    args = build_parser().parse_args(argv)

    try:
        documents = read_normalized_documents(args.input_json)
        chunker = create_chunker(
            config=ParentChildChunkingConfig(
                parent_target_tokens=args.parent_target_tokens,
                parent_hard_max_tokens=args.parent_hard_max_tokens,
                child_target_tokens=args.child_target_tokens,
                child_overlap_tokens=args.child_overlap_tokens,
                include_context_prefix=not args.no_context_prefix,
            )
        )
        chunked_documents = [chunker.chunk(document) for document in documents]
    except Exception as exc:
        print_error(exc)
        return 1

    if args.output_json is not None:
        write_chunked_documents_json(chunked_documents, args.output_json)
        print(f"Wrote chunk JSON output to: {args.output_json}")

    if args.dump_json:
        print_chunked_documents_json(chunked_documents)
    else:
        print_summary(
            chunked_documents,
            max_documents=args.max_documents,
            max_children=args.max_children,
        )

    return 0


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-chunk",
        description="Create structure-aware parent-child chunks from normalized JSON.",
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="ParsedDocument JSON file produced by docu-parse --output-json.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help=(
            "Write complete ChunkedDocument JSON to a file. For multiple "
            "documents, writes a JSON array."
        ),
    )
    parser.add_argument(
        "--dump-json",
        action="store_true",
        help="Print the complete ChunkedDocument JSON to stdout.",
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
        "--max-documents",
        type=int,
        default=10,
        help="Maximum documents to show in the terminal summary. Use 0 for all.",
    )
    parser.add_argument(
        "--max-children",
        type=int,
        default=3,
        help="Maximum child chunk previews per document. Use 0 for all.",
    )
    return parser


def read_normalized_documents(input_path: Path) -> list[ParsedDocument]:
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
            raise ValueError("input JSON must contain at least one document")
        return [ParsedDocument.model_validate(item) for item in payload]

    if isinstance(payload, dict):
        return [ParsedDocument.model_validate(payload)]

    raise ValueError("input JSON must be a ParsedDocument object or list")


def write_chunked_documents_json(
    chunked_documents: list[ChunkedDocument],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = chunked_documents_json_payload(chunked_documents)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_chunked_documents_json(chunked_documents: list[ChunkedDocument]) -> None:
    payload = chunked_documents_json_payload(chunked_documents)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def chunked_documents_json_payload(chunked_documents: list[ChunkedDocument]) -> Any:
    if len(chunked_documents) == 1:
        return chunked_documents[0].model_dump(mode="json")

    return [document.model_dump(mode="json") for document in chunked_documents]


def print_summary(
    chunked_documents: list[ChunkedDocument],
    *,
    max_documents: int,
    max_children: int,
) -> None:
    document_limit = (
        len(chunked_documents)
        if max_documents == 0
        else min(max_documents, len(chunked_documents))
    )
    total_parent_count = sum(len(document.parent_chunks) for document in chunked_documents)
    total_child_count = sum(len(document.child_chunks) for document in chunked_documents)

    print("CHUNKING SUMMARY")
    print(f"  document_count: {len(chunked_documents)}")
    print(f"  parent_chunk_count: {total_parent_count}")
    print(f"  child_chunk_count: {total_child_count}")
    print()

    for chunked_document in chunked_documents[:document_limit]:
        print_document_summary(chunked_document, max_children=max_children)

    if document_limit < len(chunked_documents):
        remaining_count = len(chunked_documents) - document_limit
        print(f"... {remaining_count} more document(s). Use --max-documents 0 to show all.")


def print_document_summary(
    chunked_document: ChunkedDocument,
    *,
    max_children: int,
) -> None:
    print("=" * 100)
    print(f"DOCUMENT: {chunked_document.file_name}")
    print(f"  title: {chunked_document.title}")
    print(f"  file_type: {chunked_document.file_type}")
    print(f"  parent_chunks: {len(chunked_document.parent_chunks)}")
    print(f"  child_chunks: {len(chunked_document.child_chunks)}")

    child_limit = (
        len(chunked_document.child_chunks)
        if max_children == 0
        else min(max_children, len(chunked_document.child_chunks))
    )
    print(f"  showing_child_chunks: {child_limit}")

    for child in chunked_document.child_chunks[:child_limit]:
        print("-" * 80)
        print(f"  [{child.child_index}] parent={child.parent_chunk_id}")
        print(f"    tokens: {child.token_count}")
        if child.parent_path:
            print(f"    parent_path: {' > '.join(child.parent_path)}")
        if child.source_refs:
            print(f"    source_refs: {', '.join(child.source_refs)}")
        print("    text:")
        print(indent_text(preview_text(child.text), spaces=6))

    if child_limit < len(chunked_document.child_chunks):
        remaining_count = len(chunked_document.child_chunks) - child_limit
        print(f"  ... {remaining_count} more child chunk(s). Use --max-children 0 to show all.")


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
        print("ERROR: INVALID_NORMALIZED_DOCUMENT", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return

    print(f"ERROR: {exc}", file=sys.stderr)


def preview_text(text: str, *, max_length: int = 300) -> str:
    normalized_text = text.strip()
    if len(normalized_text) <= max_length:
        return normalized_text

    return normalized_text[: max_length - 3].rstrip() + "..."


def indent_text(text: str, *, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines() or [""])


if __name__ == "__main__":
    raise SystemExit(main())
