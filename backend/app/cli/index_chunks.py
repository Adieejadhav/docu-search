from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import AppError
from app.core.env import load_environment
from app.ingestion.chunking import ChunkedDocument
from app.embeddings import LocalSentenceTransformerEmbeddingProvider
from app.indexing import PgVectorChunkIndex


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    load_environment()
    args = build_parser().parse_args(argv)

    try:
        documents = read_chunked_documents(args.input_json)
        index = PgVectorChunkIndex(
            database_url=args.database_url,
            embedding_provider=LocalSentenceTransformerEmbeddingProvider(
                model=args.embedding_model,
                dimensions=args.embedding_dimensions,
                batch_size=args.embedding_batch_size,
                device=args.embedding_device,
            ),
        )
        if args.clear:
            index.clear()
        indexed_child_count = index.index_documents(documents, replace=not args.no_replace)
        stats = index.stats()
    except Exception as exc:
        print_error(exc)
        return 1

    print("INDEX SUMMARY")
    print(
        "  database_url: "
        f"{redact_database_url(args.database_url or os.getenv('DATABASE_URL', 'DATABASE_URL'))}"
    )
    print(f"  input_documents: {len(documents)}")
    print(f"  indexed_child_chunks: {indexed_child_count}")
    print(f"  total_documents: {stats.document_count}")
    print(f"  total_parent_chunks: {stats.parent_chunk_count}")
    print(f"  total_child_chunks: {stats.child_chunk_count}")
    print(f"  embedding_model: {stats.embedding_model}")
    print(f"  embedding_dimensions: {stats.embedding_dimensions}")
    return 0


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-index",
        description="Persist chunk JSON into PostgreSQL + pgvector.",
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="ChunkedDocument JSON file produced by docu-chunk --output-json.",
    )
    parser.add_argument("--database-url", help="PostgreSQL DATABASE_URL.")
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
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the index before inserting documents.",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Do not delete matching document IDs before upsert.",
    )
    return parser


def redact_database_url(database_url: str) -> str:
    if database_url == "DATABASE_URL" or "@" not in database_url:
        return database_url

    scheme_and_credentials, host = database_url.split("@", 1)
    scheme = scheme_and_credentials.split("://", 1)[0]
    return f"{scheme}://***@{host}"


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


if __name__ == "__main__":
    raise SystemExit(main())
