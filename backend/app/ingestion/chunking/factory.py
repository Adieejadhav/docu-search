"""
File: backend/app/ingestion/chunking/factory.py
Purpose: Creates chunker instances by strategy name.
"""

from __future__ import annotations

from app.core.exceptions import ChunkingError

from .strategies.base import ParentChildChunkingConfig
from .strategies.parent_child_chunker import StructureAwareParentChildChunker


def create_chunker(
    strategy: str = StructureAwareParentChildChunker.STRATEGY_NAME,
    *,
    config: ParentChildChunkingConfig | None = None,
) -> StructureAwareParentChildChunker:
    normalized_strategy = strategy.strip().lower()
    if normalized_strategy == StructureAwareParentChildChunker.STRATEGY_NAME:
        return StructureAwareParentChildChunker(config=config)

    raise ChunkingError(
        f"Unsupported chunking strategy: {strategy}",
        code="UNSUPPORTED_CHUNKING_STRATEGY",
        details={"strategy": strategy},
    )
