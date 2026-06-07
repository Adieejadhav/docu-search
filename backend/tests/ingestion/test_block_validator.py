from __future__ import annotations

import pytest

from app.core.constants import BlockType
from app.core.exceptions import DocumentBlockValidationError
from app.ingestion.normalizers.block_schema import DocumentBlock
from app.ingestion.validators.block_validator import validate_blocks


def test_validate_blocks_accepts_contiguous_unique_blocks():
    blocks = [
        DocumentBlock(
            block_type=BlockType.PARAGRAPH,
            text="First",
            order=0,
        ),
        DocumentBlock(
            block_type=BlockType.PARAGRAPH,
            text="Second",
            order=1,
        ),
    ]

    assert validate_blocks(blocks) == blocks


def test_validate_blocks_rejects_non_contiguous_order():
    blocks = [
        DocumentBlock(
            block_type=BlockType.PARAGRAPH,
            text="First",
            order=1,
        )
    ]

    with pytest.raises(DocumentBlockValidationError) as error:
        validate_blocks(blocks)

    assert error.value.code == "INVALID_BLOCK_ORDER"


def test_validate_blocks_rejects_duplicate_ids():
    blocks = [
        DocumentBlock(
            id="same-id",
            block_type=BlockType.PARAGRAPH,
            text="First",
            order=0,
        ),
        DocumentBlock(
            id="same-id",
            block_type=BlockType.PARAGRAPH,
            text="Second",
            order=1,
        ),
    ]

    with pytest.raises(DocumentBlockValidationError) as error:
        validate_blocks(blocks)

    assert error.value.code == "DUPLICATE_BLOCK_ID"
