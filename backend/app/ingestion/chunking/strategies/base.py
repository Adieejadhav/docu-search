"""
File: backend/app/ingestion/chunking/strategies/base.py
Purpose: Shared configuration and internal segment types for chunking strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ingestion.normalizers.block_schema import DocumentBlock


@dataclass(frozen=True)
class ParentChildChunkingConfig:
    """
    Tunable boundaries for structure-aware parent-child chunking.
    """

    parent_target_tokens: int = 1200
    parent_hard_max_tokens: int = 2000
    child_target_tokens: int = 350
    child_overlap_tokens: int = 60
    include_context_prefix: bool = True

    def __post_init__(self) -> None:
        if self.parent_target_tokens < 1:
            raise ValueError("parent_target_tokens must be greater than zero")

        if self.parent_hard_max_tokens < self.parent_target_tokens:
            raise ValueError(
                "parent_hard_max_tokens must be greater than or equal to "
                "parent_target_tokens"
            )

        if self.child_target_tokens < 1:
            raise ValueError("child_target_tokens must be greater than zero")

        if self.child_overlap_tokens < 0:
            raise ValueError("child_overlap_tokens cannot be negative")

        if self.child_overlap_tokens >= self.child_target_tokens:
            raise ValueError("child_overlap_tokens must be smaller than child target")


@dataclass
class StructureGroup:
    """
    Consecutive normalized blocks that share one source structure.
    """

    key: str
    title: str
    parent_path: list[str]
    blocks: list[DocumentBlock] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BlockSegment:
    """
    A source block or deterministic slice of a large source block.
    """

    block: DocumentBlock
    text: str
    segment_index: int = 0
    segment_count: int = 1
