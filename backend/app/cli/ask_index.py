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
from app.llm import OllamaChatClient
from app.rag import RagAnswer, RagAnswerer


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
        retrieval_result = index.retrieve(
            args.query,
            top_k=args.top_k,
            metadata_filters=build_metadata_filters(args),
        )
        answer = RagAnswerer(
            llm_client=OllamaChatClient(
                model=args.ollama_model,
                host=args.ollama_host,
                temperature=args.temperature,
            )
        ).answer(retrieval_result)
    except Exception as exc:
        print_error(exc)
        return 1

    if args.output_json is not None:
        write_answer_json(answer, args.output_json)
        print(f"Wrote RAG answer JSON output to: {args.output_json}")

    if args.dump_json:
        print_answer_json(answer)
    else:
        print_summary(answer, show_context=args.show_context)

    return 0


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-ask",
        description="Ask a question using pgvector retrieval plus Ollama generation.",
    )
    parser.add_argument("query", help="Question to answer from the indexed documents.")
    parser.add_argument("--database-url", help="PostgreSQL DATABASE_URL.")
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved child chunk matches to ground the answer.",
    )
    parser.add_argument("--file-name", help="Optional exact file_name filter.")
    parser.add_argument("--file-type", help="Optional exact file_type filter.")
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
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", OllamaChatClient.DEFAULT_HOST),
        help="Ollama host URL.",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.getenv("OLLAMA_MODEL", OllamaChatClient.DEFAULT_MODEL),
        help="Ollama model used for answer generation.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.getenv("OLLAMA_TEMPERATURE", "0")),
        help="Ollama generation temperature.",
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print retrieved context summaries below the generated answer.",
    )
    parser.add_argument(
        "--dump-json",
        action="store_true",
        help="Print the complete RAG answer JSON.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Write the complete RAG answer JSON to a file.",
    )
    return parser


def build_metadata_filters(args: argparse.Namespace) -> dict[str, Any] | None:
    filters: dict[str, Any] = {}
    if args.file_name:
        filters["file_name"] = args.file_name
    if args.file_type:
        filters["file_type"] = args.file_type

    return filters or None


def write_answer_json(answer: RagAnswer, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(answer.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_answer_json(answer: RagAnswer) -> None:
    print(json.dumps(answer.model_dump(mode="json"), indent=2, ensure_ascii=False))


def print_summary(answer: RagAnswer, *, show_context: bool) -> None:
    retrieval = answer.retrieval_result
    print("RAG ANSWER")
    print(f"  query: {answer.query}")
    print(f"  llm_model: {answer.llm_model}")
    print(f"  embedding_model: {retrieval.embedding_model}")
    print(f"  returned_results: {len(retrieval.results)}")
    print()
    print(answer.answer)
    print()
    print("CITATIONS")
    for citation in answer.citations:
        source_refs = ", ".join(citation.get("source_refs") or [])
        parent_path = " > ".join(citation.get("parent_path") or [])
        print(
            f"  [{citation['rank']}] score={citation['score']:.4f} "
            f"file={citation.get('file_name')}"
        )
        if source_refs:
            print(f"      source_refs: {source_refs}")
        if parent_path:
            print(f"      parent_path: {parent_path}")

    if show_context:
        print()
        print("RETRIEVED CONTEXT")
        for item in retrieval.results:
            print("=" * 100)
            print(f"[{item.rank}] {item.metadata.get('file_name')}")
            print(indent_text(preview_text(item.parent_chunk.text, max_length=900), spaces=2))


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
        print("ERROR: INVALID_RAG_ANSWER", file=sys.stderr)
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
