from __future__ import annotations

import argparse
import glob
import json
import logging
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.core.exceptions import AppError
from app.core.observability import OperationMetricsRecorder
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument
from app.ingestion.parsers.factory import ParserFactory
from app.ingestion.validators.file_validator import should_skip_ingestion_file


class ParseLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        for field_name in (
            "parse_parser",
            "parse_extension",
            "parse_duration_ms",
            "parse_block_count",
            "parse_error_code",
            "parse_file_name",
        ):
            if not hasattr(record, field_name):
                setattr(record, field_name, "-")

        return super().format(record)


def main(argv: list[str] | None = None) -> int:
    configure_terminal_encoding()
    args = build_parser().parse_args(argv)
    metrics_recorder = OperationMetricsRecorder()
    parser_logger = logging.getLogger("app.ingestion.parsers.factory")
    logger_state = snapshot_logger_state(parser_logger)

    try:
        logger = configure_logging(enabled=not args.no_logs, level=args.log_level)
        factory = ParserFactory(metrics_recorder=metrics_recorder, logger=logger)
        paths = list(
            resolve_input_paths(args.paths, recursive=args.recursive, factory=factory)
        )

        if not paths:
            print("No input files found.", file=sys.stderr)
            return 2

        exit_code = 0
        parsed_documents: list[ParsedDocument] = []
        for path in paths:
            print_file_header(path)
            try:
                document = factory.parse_document(path)
            except Exception as exc:
                exit_code = 1
                print_parse_error(exc)
                continue

            if args.output_json is not None:
                parsed_documents.append(document)
                print_document(
                    document,
                    max_blocks=args.max_blocks,
                    full_text=args.full_text,
                )
            elif args.dump_json:
                print_document_json(document)
            else:
                print_document(
                    document,
                    max_blocks=args.max_blocks,
                    full_text=args.full_text,
                )

        if args.output_json is not None:
            write_documents_json(parsed_documents, args.output_json)
            print()
            print(f"Wrote full JSON output to: {args.output_json}")

        print_metrics_summary(metrics_recorder)
        return exit_code
    finally:
        restore_logger_state(parser_logger, logger_state)


def configure_terminal_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docu-parse",
        description=(
            "Inspect parser output and observability logs for real document files."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files, directories, or glob patterns to parse.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan directory inputs and recursive glob patterns.",
    )
    parser.add_argument(
        "--max-blocks",
        type=int,
        default=10,
        help="Maximum blocks to print per document. Use 0 for all blocks.",
    )
    parser.add_argument(
        "--full-text",
        action="store_true",
        help="Print full block text instead of a shortened preview.",
    )
    parser.add_argument(
        "--dump-json",
        action="store_true",
        help="Print the complete ParsedDocument as JSON.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help=(
            "Write complete ParsedDocument JSON to a file. For multiple inputs, "
            "writes a JSON array."
        ),
    )
    parser.add_argument(
        "--no-logs",
        action="store_true",
        help="Hide parser observability log lines.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
        help="Parser observability log level.",
    )
    return parser


def configure_logging(*, enabled: bool, level: str) -> logging.Logger:
    logger = logging.getLogger("app.ingestion.parsers.factory")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.CRITICAL + 1 if not enabled else getattr(logging, level))

    if enabled:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            ParseLogFormatter(
                "%(levelname)s %(message)s "
                "parser=%(parse_parser)s "
                "file=%(parse_file_name)s "
                "ext=%(parse_extension)s "
                "duration_ms=%(parse_duration_ms)s "
                "blocks=%(parse_block_count)s "
                "error=%(parse_error_code)s"
            )
        )
        logger.addHandler(handler)

    return logger


def snapshot_logger_state(logger: logging.Logger) -> dict[str, Any]:
    return {
        "handlers": list(logger.handlers),
        "level": logger.level,
        "propagate": logger.propagate,
        "disabled": logger.disabled,
    }


def restore_logger_state(logger: logging.Logger, state: dict[str, Any]) -> None:
    logger.handlers.clear()
    logger.handlers.extend(state["handlers"])
    logger.setLevel(state["level"])
    logger.propagate = state["propagate"]
    logger.disabled = state["disabled"]


def resolve_input_paths(
    inputs: Iterable[str],
    *,
    recursive: bool,
    factory: ParserFactory,
) -> Iterable[Path]:
    seen_paths: set[Path] = set()

    for raw_input in inputs:
        matches = expand_input(raw_input, recursive=recursive)

        for path in matches:
            if path.is_dir():
                yield from iter_directory_files(
                    path,
                    recursive=recursive,
                    supported_extensions=factory.supported_extensions,
                    seen_paths=seen_paths,
                )
                continue

            resolved_path = path.resolve()
            if resolved_path in seen_paths or should_skip_ingestion_file(path):
                continue

            seen_paths.add(resolved_path)
            yield path


def expand_input(raw_input: str, *, recursive: bool) -> list[Path]:
    if has_glob_pattern(raw_input):
        matches = glob.glob(raw_input, recursive=recursive)
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


def print_file_header(path: Path) -> None:
    print()
    print("=" * 100)
    print(f"FILE: {path}")
    print("=" * 100)


def print_parse_error(exc: Exception) -> None:
    if isinstance(exc, AppError):
        print(f"ERROR: {exc.code}: {exc.message}")
        if exc.details:
            print("DETAILS:")
            print(json.dumps(exc.details, indent=2, sort_keys=True, default=str))
        return

    print(f"ERROR: {exc.__class__.__name__}: {exc}")


def print_document(
    document: ParsedDocument,
    *,
    max_blocks: int,
    full_text: bool,
) -> None:
    print("DOCUMENT")
    print(f"  title: {document.title}")
    print(f"  file_name: {document.file_name}")
    print(f"  file_type: {document.file_type}")
    print(f"  source_path: {document.source_path}")
    print(f"  block_count: {len(document.blocks)}")

    if document.metadata:
        print("  metadata:")
        for key, value in sorted(document.metadata.items()):
            print(f"    {key}: {format_value(value)}")

    print()
    print_blocks(document.blocks, max_blocks=max_blocks, full_text=full_text)


def print_blocks(
    blocks: list[DocumentBlock],
    *,
    max_blocks: int,
    full_text: bool,
) -> None:
    block_limit = len(blocks) if max_blocks == 0 else min(max_blocks, len(blocks))
    print(f"BLOCKS showing {block_limit} of {len(blocks)}")

    for block in blocks[:block_limit]:
        print("-" * 80)
        print(f"[{block.order}] {block.block_type}")
        if block.level is not None:
            print(f"  level: {block.level}")
        if block.parent_path:
            print(f"  parent_path: {' > '.join(block.parent_path)}")

        location = compact_source_location(block)
        if location:
            print(f"  source_location: {location}")

        if block.metadata:
            print("  metadata:")
            for key, value in sorted(block.metadata.items()):
                print(f"    {key}: {format_value(value)}")

        print("  text:")
        print(indent_text(block.text if full_text else preview_text(block.text), spaces=4))

    if block_limit < len(blocks):
        remaining_count = len(blocks) - block_limit
        print("-" * 80)
        print(f"... {remaining_count} more block(s). Use --max-blocks 0 to show all.")


def print_document_json(document: ParsedDocument) -> None:
    print(json.dumps(document.model_dump(mode="json"), indent=2, ensure_ascii=False))


def write_documents_json(documents: list[ParsedDocument], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload: Any
    if len(documents) == 1:
        payload = documents[0].model_dump(mode="json")
    else:
        payload = [document.model_dump(mode="json") for document in documents]

    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def print_metrics_summary(metrics_recorder: OperationMetricsRecorder) -> None:
    snapshot = metrics_recorder.snapshot()

    print()
    print("=" * 100)
    print("OBSERVABILITY METRICS")
    print("=" * 100)
    print(f"total_count: {snapshot.total_count}")
    print(f"success_count: {snapshot.success_count}")
    print(f"failure_count: {snapshot.failure_count}")
    print(f"success_by_operation: {snapshot.success_by_operation}")
    print(f"failure_by_operation: {snapshot.failure_by_operation}")
    print(f"failure_by_code: {snapshot.failure_by_code}")
    print(f"total_duration_ms_by_operation: {snapshot.total_duration_ms_by_operation}")


def compact_source_location(block: DocumentBlock) -> str:
    source_location = block.source_location
    parts: list[str] = []

    for field_name in (
        "page_number",
        "line_start",
        "line_end",
        "slide_number",
        "sheet_name",
        "row_start",
        "row_end",
    ):
        value = getattr(source_location, field_name)
        if value is not None:
            parts.append(f"{field_name}={value}")

    return ", ".join(parts)


def preview_text(text: str, *, max_length: int = 500) -> str:
    normalized_text = text.strip()
    if len(normalized_text) <= max_length:
        return normalized_text

    return normalized_text[: max_length - 3].rstrip() + "..."


def indent_text(text: str, *, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.splitlines() or [""])


def format_value(value: Any) -> str:
    if isinstance(value, str):
        return value

    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
