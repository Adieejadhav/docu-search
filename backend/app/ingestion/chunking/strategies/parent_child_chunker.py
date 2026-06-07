"""
File: backend/app/ingestion/chunking/strategies/parent_child_chunker.py
Purpose: Implements structure-aware parent-child document chunking.
"""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from typing import Any

from app.ingestion.chunking.chunk_schema import (
    ChildChunk,
    ChunkedDocument,
    ParentChunk,
)
from app.ingestion.chunking.token_counter import ApproximateTokenCounter
from app.ingestion.normalizers.block_schema import DocumentBlock, ParsedDocument

from .base import BlockSegment, ParentChildChunkingConfig, StructureGroup
from .structure_grouper import StructureGrouper
from .table_chunker import AtomicBlockPolicy


class StructureAwareParentChildChunker:
    """
    Builds parent chunks from normalized document structure and child chunks
    from the smaller searchable units inside those parents.
    """

    STRATEGY_NAME = "structure_aware_parent_child"

    def __init__(
        self,
        *,
        config: ParentChildChunkingConfig | None = None,
        token_counter: ApproximateTokenCounter | None = None,
        structure_grouper: StructureGrouper | None = None,
        atomic_block_policy: AtomicBlockPolicy | None = None,
    ) -> None:
        self.config = config or ParentChildChunkingConfig()
        self._token_counter = token_counter or ApproximateTokenCounter()
        self._structure_grouper = structure_grouper or StructureGrouper()
        self._atomic_block_policy = atomic_block_policy or AtomicBlockPolicy()

    def chunk(self, document: ParsedDocument) -> ChunkedDocument:
        document_id = self._document_id(document)
        parent_chunks: list[ParentChunk] = []
        child_chunks: list[ChildChunk] = []

        for group in self._structure_grouper.group(document):
            for parent_segments in self._parent_segment_groups(group):
                parent_index = len(parent_chunks)
                parent_id = self._chunk_id(
                    document_id,
                    "parent",
                    str(parent_index),
                    group.key,
                    self._source_fingerprint(parent_segments),
                )
                parent_text = self._format_chunk_text(
                    document=document,
                    parent_path=group.parent_path,
                    text_parts=[segment.text for segment in parent_segments],
                )
                parent_chunks.append(
                    ParentChunk(
                        id=parent_id,
                        document_id=document_id,
                        parent_index=parent_index,
                        text=parent_text,
                        token_count=max(1, self._token_counter.count(parent_text)),
                        source_block_ids=self._source_block_ids(parent_segments),
                        source_refs=self._source_refs(parent_segments),
                        parent_path=group.parent_path,
                        metadata=self._chunk_metadata(
                            group=group,
                            segments=parent_segments,
                            search_level="parent",
                        ),
                    )
                )

                for child_segments in self._child_segment_groups(parent_segments):
                    child_index = len(child_chunks)
                    child_text = self._format_chunk_text(
                        document=document,
                        parent_path=group.parent_path,
                        text_parts=[segment.text for segment in child_segments],
                    )
                    child_chunks.append(
                        ChildChunk(
                            id=self._chunk_id(
                                document_id,
                                "child",
                                str(child_index),
                                parent_id,
                                self._source_fingerprint(child_segments),
                            ),
                            document_id=document_id,
                            parent_chunk_id=parent_id,
                            child_index=child_index,
                            text=child_text,
                            token_count=max(
                                1,
                                self._token_counter.count(child_text),
                            ),
                            source_block_ids=self._source_block_ids(child_segments),
                            source_refs=self._source_refs(child_segments),
                            parent_path=group.parent_path,
                            metadata=self._chunk_metadata(
                                group=group,
                                segments=child_segments,
                                search_level="child",
                            ),
                        )
                    )

        return ChunkedDocument(
            document_id=document_id,
            title=document.title,
            file_name=document.file_name,
            file_type=document.file_type,
            source_path=document.source_path,
            parent_chunks=parent_chunks,
            child_chunks=child_chunks,
            metadata={
                "chunking_strategy": self.STRATEGY_NAME,
                "parent_target_tokens": self.config.parent_target_tokens,
                "parent_hard_max_tokens": self.config.parent_hard_max_tokens,
                "child_target_tokens": self.config.child_target_tokens,
                "child_overlap_tokens": self.config.child_overlap_tokens,
                "token_counter": "approximate_whitespace",
                "parent_chunk_count": len(parent_chunks),
                "child_chunk_count": len(child_chunks),
            },
        )

    def _parent_segment_groups(
        self,
        group: StructureGroup,
    ) -> list[list[BlockSegment]]:
        source_segments = [
            segment
            for block in group.blocks
            for segment in self._segments_for_parent(block)
        ]
        return self._pack_segments(
            source_segments,
            target_tokens=self.config.parent_target_tokens,
            overlap_tokens=0,
        )

    def _child_segment_groups(
        self,
        parent_segments: list[BlockSegment],
    ) -> list[list[BlockSegment]]:
        source_segments = [
            segment
            for parent_segment in parent_segments
            for segment in self._segments_for_child(parent_segment)
        ]
        return self._pack_segments(
            source_segments,
            target_tokens=self.config.child_target_tokens,
            overlap_tokens=self.config.child_overlap_tokens,
        )

    def _segments_for_parent(self, block: DocumentBlock) -> list[BlockSegment]:
        return self._split_block(
            block=block,
            text=block.text,
            hard_max_tokens=self.config.parent_hard_max_tokens,
            target_tokens=self.config.parent_target_tokens,
            overlap_tokens=0,
        )

    def _segments_for_child(self, parent_segment: BlockSegment) -> list[BlockSegment]:
        return self._split_block(
            block=parent_segment.block,
            text=parent_segment.text,
            hard_max_tokens=self.config.child_target_tokens,
            target_tokens=self.config.child_target_tokens,
            overlap_tokens=self.config.child_overlap_tokens,
        )

    def _split_block(
        self,
        *,
        block: DocumentBlock,
        text: str,
        hard_max_tokens: int,
        target_tokens: int,
        overlap_tokens: int,
    ) -> list[BlockSegment]:
        token_count = self._token_counter.count(text)
        if token_count <= hard_max_tokens:
            return [BlockSegment(block=block, text=text)]

        pieces = self._token_counter.split(
            text,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )
        return [
            BlockSegment(
                block=block,
                text=piece,
                segment_index=index,
                segment_count=len(pieces),
            )
            for index, piece in enumerate(pieces)
        ]

    def _pack_segments(
        self,
        segments: list[BlockSegment],
        *,
        target_tokens: int,
        overlap_tokens: int,
    ) -> list[list[BlockSegment]]:
        groups: list[list[BlockSegment]] = []
        current: list[BlockSegment] = []
        current_tokens = 0

        for segment in segments:
            segment_tokens = max(1, self._token_counter.count(segment.text))
            if current and current_tokens + segment_tokens > target_tokens:
                groups.append(current)
                current = self._trailing_overlap(current, overlap_tokens)
                current_tokens = self._segments_token_count(current)
                if current and current_tokens + segment_tokens > target_tokens:
                    current = []
                    current_tokens = 0

            current.append(segment)
            current_tokens += segment_tokens

        if current:
            groups.append(current)

        return groups

    def _trailing_overlap(
        self,
        segments: list[BlockSegment],
        overlap_tokens: int,
    ) -> list[BlockSegment]:
        if overlap_tokens <= 0:
            return []

        tail: list[BlockSegment] = []
        tail_tokens = 0
        for segment in reversed(segments):
            segment_tokens = max(1, self._token_counter.count(segment.text))
            if tail_tokens + segment_tokens > overlap_tokens:
                break
            tail.insert(0, segment)
            tail_tokens += segment_tokens

        return tail

    def _format_chunk_text(
        self,
        *,
        document: ParsedDocument,
        parent_path: list[str],
        text_parts: Iterable[str],
    ) -> str:
        body = "\n\n".join(part.strip() for part in text_parts if part.strip())
        if not self.config.include_context_prefix:
            return body

        prefix_parts = [f"Document: {document.title}"]
        if parent_path:
            prefix_parts.append("Section: " + " > ".join(parent_path))

        if not body:
            return "\n".join(prefix_parts)

        return "\n".join([*prefix_parts, "", body])

    def _chunk_metadata(
        self,
        *,
        group: StructureGroup,
        segments: list[BlockSegment],
        search_level: str,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "search_level": search_level,
            "structure_key": group.key,
            "structure_title": group.title,
            "structure": group.metadata,
            "block_orders": self._unique_ints(
                segment.block.order for segment in segments
            ),
            "block_types": self._unique_strings(
                str(segment.block.block_type) for segment in segments
            ),
        }

        split_segments = [
            {
                "block_id": segment.block.id,
                "segment_index": segment.segment_index,
                "segment_count": segment.segment_count,
            }
            for segment in segments
            if segment.segment_count > 1
        ]
        if split_segments:
            metadata["split_segments"] = split_segments

        return metadata

    def _source_block_ids(self, segments: list[BlockSegment]) -> list[str]:
        return self._unique_strings(segment.block.id for segment in segments)

    def _source_refs(self, segments: list[BlockSegment]) -> list[str]:
        refs = (
            str(segment.block.metadata["source_ref"])
            for segment in segments
            if segment.block.metadata.get("source_ref")
        )
        return self._unique_strings(refs)

    def _source_fingerprint(self, segments: list[BlockSegment]) -> str:
        parts = [
            (
                f"{segment.block.order}:"
                f"{self._block_source_ref(segment.block)}:"
                f"{segment.segment_index}:"
                f"{segment.segment_count}"
            )
            for segment in segments
        ]
        return "|".join(parts)

    def _block_source_ref(self, block: DocumentBlock) -> str:
        source_ref = block.metadata.get("source_ref")
        if source_ref:
            return str(source_ref)

        location = block.source_location
        location_parts = [
            str(location.page_number or ""),
            str(location.line_start or ""),
            str(location.line_end or ""),
            str(location.slide_number or ""),
            location.sheet_name or "",
            str(location.row_start or ""),
            str(location.row_end or ""),
        ]
        if any(location_parts):
            return ":".join(location_parts)

        json_path = block.metadata.get("json_path")
        if json_path:
            return str(json_path)

        return "no-source"

    def _segments_token_count(self, segments: list[BlockSegment]) -> int:
        return sum(
            max(1, self._token_counter.count(segment.text)) for segment in segments
        )

    def _document_id(self, document: ParsedDocument) -> str:
        return self._chunk_id(
            "document",
            document.source_path or "",
            document.file_name,
            document.title,
            str(document.file_type),
        )

    def _chunk_id(self, *parts: str) -> str:
        digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return digest[:24]

    def _unique_strings(self, values: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values

    def _unique_ints(self, values: Iterable[int]) -> list[int]:
        seen: set[int] = set()
        unique_values: list[int] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        return unique_values
