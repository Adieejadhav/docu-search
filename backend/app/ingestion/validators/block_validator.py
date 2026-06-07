"""
File: backend/app/ingestion/validators/block_validator.py
Purpose: Provides reusable validation helpers for normalized document blocks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.core.constants import BlockType
from app.core.exceptions import DocumentBlockValidationError

if TYPE_CHECKING:
    from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument


def strip_text(value: str) -> str:
    """
    Strip leading and trailing whitespace.

    This does not enforce non-empty text because PAGE_BREAK blocks
    may intentionally have empty text.
    """
    return value.strip().lstrip("\ufeff")


def clean_required_text(value: str, field_name: str = "value") -> str:
    """
    Strip and validate required string fields such as title and file_name.
    """
    cleaned = strip_text(value)

    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")

    return cleaned


def clean_optional_text(value: str | None) -> str | None:
    """
    Strip optional text fields and convert empty strings to None.
    """
    if value is None:
        return None

    cleaned = strip_text(value)
    return cleaned or None


def validate_number_range(
    *,
    start: int | None,
    end: int | None,
    start_name: str,
    end_name: str,
) -> None:
    """
    Validate that an end value is not smaller than a start value.
    """
    if start is not None and end is not None and end < start:
        raise ValueError(f"{end_name} cannot be less than {start_name}")


def is_block_type(value: object, expected: BlockType) -> bool:
    """
    Compare block type safely even when Pydantic stores enum values as strings.
    """
    return value == expected or value == expected.value


def validate_document_block_rules(
    *,
    block_type: BlockType | str,
    text: str,
    level: int | None,
) -> None:
    """
    Validate cross-field rules for normalized document blocks.
    """
    if not is_block_type(block_type, BlockType.PAGE_BREAK) and not text.strip():
        raise ValueError("text cannot be empty for content blocks")

    if is_block_type(block_type, BlockType.HEADING) and level is None:
        raise ValueError("heading block must have a level")

    if not is_block_type(block_type, BlockType.HEADING) and level is not None:
        raise ValueError("level should only be set for heading blocks")


def validate_blocks(blocks: Sequence[DocumentBlock]) -> list[DocumentBlock]:
    """
    Validate parser block invariants that span more than one Pydantic model.
    """
    if not blocks:
        raise DocumentBlockValidationError(
            "Parsed document must contain at least one block",
            code="EMPTY_BLOCKS",
        )

    seen_ids: set[str] = set()

    for expected_order, block in enumerate(blocks):
        if block.id in seen_ids:
            raise DocumentBlockValidationError(
                "Duplicate block id found",
                code="DUPLICATE_BLOCK_ID",
                details={"block_id": block.id},
            )
        seen_ids.add(block.id)

        if block.order != expected_order:
            raise DocumentBlockValidationError(
                "Block order must be contiguous and zero-based",
                code="INVALID_BLOCK_ORDER",
                details={
                    "block_id": block.id,
                    "expected_order": expected_order,
                    "actual_order": block.order,
                },
            )

        try:
            validate_document_block_rules(
                block_type=block.block_type,
                text=block.text,
                level=block.level,
            )
        except ValueError as exc:
            raise DocumentBlockValidationError(
                str(exc),
                code="INVALID_BLOCK",
                details={"block_id": block.id, "order": block.order},
            ) from exc

    return list(blocks)


def validate_parsed_document(document: ParsedDocument) -> ParsedDocument:
    validate_blocks(document.blocks)
    return document
