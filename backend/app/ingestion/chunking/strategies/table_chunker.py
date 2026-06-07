"""
File: backend/app/ingestion/chunking/strategies/table_chunker.py
Purpose: Table/code-aware helpers used by parent-child chunking.
"""

from __future__ import annotations

from app.core.constants import BlockType
from app.ingestion.normalizers.block_schema import DocumentBlock
from app.ingestion.validators.block_validator import is_block_type


class AtomicBlockPolicy:
    """
    Identifies block types that should remain intact whenever they fit.
    """

    ATOMIC_BLOCK_TYPES = {
        BlockType.TABLE,
        BlockType.CODE,
        BlockType.JSON,
    }

    def is_atomic(self, block: DocumentBlock) -> bool:
        return any(
            is_block_type(block.block_type, block_type)
            for block_type in self.ATOMIC_BLOCK_TYPES
        )
