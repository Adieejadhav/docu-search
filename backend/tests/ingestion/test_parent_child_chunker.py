from __future__ import annotations

from app.core.constants import BlockType, SupportedFileType
from app.ingestion.chunking import (
    ParentChildChunkingConfig,
    StructureAwareParentChildChunker,
    chunk_document,
    create_chunker,
)
from app.ingestion.normalizers import DocumentNormalizer
from app.ingestion.normalizers.block_schema import (
    DocumentBlock,
    ParsedDocument,
    SourceLocation,
)


def test_structure_aware_chunker_preserves_parent_paths_and_source_refs():
    document = _normalized_document(
        file_type=SupportedFileType.MARKDOWN,
        blocks=[
            DocumentBlock(
                block_type=BlockType.HEADING,
                text="Aquila KB",
                order=0,
                level=1,
                source_location=SourceLocation(line_start=1, line_end=1),
            ),
            DocumentBlock(
                block_type=BlockType.HEADING,
                text="Policy Table",
                order=1,
                level=2,
                parent_path=["Aquila KB"],
                source_location=SourceLocation(line_start=3, line_end=3),
            ),
            DocumentBlock(
                block_type=BlockType.TABLE,
                text=(
                    "| Policy ID | Rule |\n"
                    "| --- | --- |\n"
                    "| P-001 | Escalate to GridOps within 10 minutes. |"
                ),
                order=2,
                parent_path=["Aquila KB", "Policy Table"],
                source_location=SourceLocation(line_start=5, line_end=7),
                metadata={"format": "markdown_table"},
            ),
        ],
    )

    chunked = chunk_document(document)
    child = next(chunk for chunk in chunked.child_chunks if "P-001" in chunk.text)

    assert child.parent_path == ["Aquila KB", "Policy Table"]
    assert "Section: Aquila KB > Policy Table" in child.text
    assert document.blocks[2].id in child.source_block_ids
    assert "lines:5-7" in child.source_refs
    assert BlockType.TABLE.value in child.metadata["block_types"]
    assert child.parent_chunk_id in {parent.id for parent in chunked.parent_chunks}


def test_chunker_splits_large_blocks_into_child_windows_with_overlap():
    words = [f"word{index}" for index in range(1, 31)]
    document = _normalized_document(
        blocks=[
            DocumentBlock(
                block_type=BlockType.PARAGRAPH,
                text=" ".join(words),
                order=0,
                source_location=SourceLocation(line_start=1, line_end=1),
            )
        ],
    )
    chunker = StructureAwareParentChildChunker(
        config=ParentChildChunkingConfig(
            parent_target_tokens=40,
            parent_hard_max_tokens=60,
            child_target_tokens=10,
            child_overlap_tokens=2,
            include_context_prefix=False,
        )
    )

    chunked = chunker.chunk(document)

    assert len(chunked.child_chunks) > 1
    assert "word9 word10" in chunked.child_chunks[1].text
    assert all(chunk.source_refs == ["lines:1"] for chunk in chunked.child_chunks)
    assert all(
        chunk.metadata["split_segments"][0]["segment_count"] > 1
        for chunk in chunked.child_chunks
    )


def test_chunker_keeps_small_table_blocks_atomic():
    document = _normalized_document(
        file_type=SupportedFileType.CSV,
        blocks=[
            DocumentBlock(
                block_type=BlockType.TABLE,
                text="id: 1 | policy: P-004 | exception: satellite sync within 14 days",
                order=0,
                source_location=SourceLocation(line_start=2, line_end=2),
                metadata={"format": "csv_row"},
            )
        ],
    )
    chunker = StructureAwareParentChildChunker(
        config=ParentChildChunkingConfig(
            parent_target_tokens=80,
            parent_hard_max_tokens=100,
            child_target_tokens=80,
            child_overlap_tokens=0,
        )
    )

    chunked = chunker.chunk(document)

    assert len(chunked.parent_chunks) == 1
    assert len(chunked.child_chunks) == 1
    assert "satellite sync within 14 days" in chunked.child_chunks[0].text
    assert chunked.child_chunks[0].source_block_ids == [document.blocks[0].id]


def test_chunk_ids_are_stable_for_same_source_structure():
    first = _normalized_document(
        blocks=[
            DocumentBlock(
                block_type=BlockType.PARAGRAPH,
                text="Stable source line.",
                order=0,
                source_location=SourceLocation(line_start=10, line_end=10),
            )
        ],
    )
    second = _normalized_document(
        blocks=[
            DocumentBlock(
                block_type=BlockType.PARAGRAPH,
                text="Stable source line.",
                order=0,
                source_location=SourceLocation(line_start=10, line_end=10),
            )
        ],
    )

    first_chunked = chunk_document(first)
    second_chunked = chunk_document(second)

    assert first.blocks[0].id != second.blocks[0].id
    assert [chunk.id for chunk in first_chunked.parent_chunks] == [
        chunk.id for chunk in second_chunked.parent_chunks
    ]
    assert [chunk.id for chunk in first_chunked.child_chunks] == [
        chunk.id for chunk in second_chunked.child_chunks
    ]


def test_create_chunker_returns_structure_aware_chunker():
    assert isinstance(create_chunker(), StructureAwareParentChildChunker)


def _normalized_document(
    *,
    blocks: list[DocumentBlock],
    file_type: SupportedFileType = SupportedFileType.TXT,
) -> ParsedDocument:
    return DocumentNormalizer().normalize(
        ParsedDocument(
            title="Example",
            file_name=f"example.{file_type.value}",
            file_type=file_type,
            source_path=f"/tmp/example.{file_type.value}",
            blocks=blocks,
        )
    )
