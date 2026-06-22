"""
File: backend/app/ingestion/pipeline_testing.py
Purpose: Runs bounded, non-destructive tests for individual ingestion pipeline layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from app.embeddings import EmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.ingestion.chunking import create_chunker
from app.ingestion.parsers.factory import ParserFactory
from app.ingestion.validators.file_validator import validate_local_file

PipelineTestStage = Literal["validate", "parse", "chunk", "embed", "index"]

PREVIEW_ITEM_LIMIT = 5
PREVIEW_TEXT_LIMIT = 500
EMBEDDING_SAMPLE_LIMIT = 3


@dataclass(frozen=True)
class PipelineNodeTestResult:
    stage: PipelineTestStage
    duration_ms: float
    summary: dict[str, Any]
    preview: list[dict[str, Any]] = field(default_factory=list)


class PipelineNodeTester:
    """Executes one pipeline stage and only the prerequisites required for it."""

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        index: PgVectorChunkIndex,
        parser_factory: ParserFactory | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.index = index
        self.parser_factory = parser_factory or ParserFactory()
        self.chunker = create_chunker()

    def run(self, *, stage: PipelineTestStage, file_path: Path) -> PipelineNodeTestResult:
        started = perf_counter()
        validated = validate_local_file(
            file_path,
            supported_extensions=set(self.parser_factory.supported_extensions),
            validate_content_type=True,
        )
        if stage == "validate":
            return self._result(
                stage=stage,
                started=started,
                summary={
                    "file_name": validated.file_name,
                    "extension": validated.extension,
                    "size_bytes": validated.size_bytes,
                    "detected_content_type": validated.detected_content_type,
                    "media_type": validated.media_type,
                },
            )

        parsed = self.parser_factory.parse_document(file_path)
        if stage == "parse":
            return self._result(
                stage=stage,
                started=started,
                summary={
                    "file_name": parsed.file_name,
                    "title": parsed.title,
                    "file_type": parsed.file_type,
                    "parser": parsed.metadata.get("parser"),
                    "block_count": len(parsed.blocks),
                    "normalization": "completed",
                },
                preview=[
                    {
                        "order": block.order,
                        "block_type": block.block_type,
                        "text": self._preview_text(block.text),
                        "parent_path": block.parent_path,
                        "source_location": block.source_location.model_dump(
                            mode="json",
                            exclude_none=True,
                        ),
                    }
                    for block in parsed.blocks[:PREVIEW_ITEM_LIMIT]
                ],
            )

        chunked = self.chunker.chunk(parsed)
        if stage == "chunk":
            return self._result(
                stage=stage,
                started=started,
                summary={
                    "document_id": chunked.document_id,
                    "parent_chunk_count": len(chunked.parent_chunks),
                    "child_chunk_count": len(chunked.child_chunks),
                    "strategy": chunked.metadata.get("chunking_strategy"),
                },
                preview=[
                    {
                        "child_chunk_id": chunk.id,
                        "parent_chunk_id": chunk.parent_chunk_id,
                        "token_count": chunk.token_count,
                        "parent_path": chunk.parent_path,
                        "source_refs": chunk.source_refs,
                        "text": self._preview_text(chunk.text),
                    }
                    for chunk in chunked.child_chunks[:PREVIEW_ITEM_LIMIT]
                ],
            )

        sample_chunks = chunked.child_chunks[:EMBEDDING_SAMPLE_LIMIT]
        vectors = self.embedding_provider.embed_texts(
            [chunk.text for chunk in sample_chunks]
        )
        vector_preview = [
            {
                "child_chunk_id": chunk.id,
                "text": self._preview_text(chunk.text, limit=220),
                "dimensions": len(vector),
                "l2_norm": round(sqrt(sum(value * value for value in vector)), 6),
                "values": [round(value, 6) for value in vector[:8]],
            }
            for chunk, vector in zip(sample_chunks, vectors, strict=True)
        ]
        if stage == "embed":
            return self._result(
                stage=stage,
                started=started,
                summary={
                    "provider": self.embedding_provider.name,
                    "dimensions": self.embedding_provider.dimensions,
                    "embedded_sample_count": len(vectors),
                    "available_child_chunks": len(chunked.child_chunks),
                },
                preview=vector_preview,
            )

        stats = self.index.stats()
        return self._result(
            stage="index",
            started=started,
            summary={
                "mode": "non_destructive_readiness_check",
                "candidate_document_id": chunked.document_id,
                "candidate_parent_chunks": len(chunked.parent_chunks),
                "candidate_child_chunks": len(chunked.child_chunks),
                "validated_vector_count": len(vectors),
                "index_document_count": stats.document_count,
                "index_parent_chunk_count": stats.parent_chunk_count,
                "index_child_chunk_count": stats.child_chunk_count,
                "index_embedding_model": stats.embedding_model,
                "index_embedding_dimensions": stats.embedding_dimensions,
            },
            preview=vector_preview,
        )

    def _result(
        self,
        *,
        stage: PipelineTestStage,
        started: float,
        summary: dict[str, Any],
        preview: list[dict[str, Any]] | None = None,
    ) -> PipelineNodeTestResult:
        return PipelineNodeTestResult(
            stage=stage,
            duration_ms=round((perf_counter() - started) * 1000, 3),
            summary=summary,
            preview=preview or [],
        )

    def _preview_text(self, value: str, *, limit: int = PREVIEW_TEXT_LIMIT) -> str:
        normalized = " ".join(value.split())
        return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."
