from __future__ import annotations

from pathlib import Path

from app.indexing import PgVectorIndexStats
from app.ingestion.pipeline_testing import PipelineNodeTester


class _FakeEmbeddingProvider:
    name = "fake-embedding-4d"
    dimensions = 4

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.5, 0.5, 0.5, 0.5] for _ in texts]


class _FakeIndex:
    def stats(self) -> PgVectorIndexStats:
        return PgVectorIndexStats(
            document_count=3,
            parent_chunk_count=8,
            child_chunk_count=15,
            embedding_model="fake-embedding-4d",
            embedding_dimensions=4,
        )


def _write_markdown(path: Path) -> Path:
    path.write_text(
        "# Password Policy\n\n"
        "Service accounts rotate every 90 days.\n\n"
        "## Exception\n\n"
        "Offline substations synchronize within 14 days.\n",
        encoding="utf-8",
    )
    return path


def test_pipeline_tester_runs_each_stage_without_mutating_index(tmp_path: Path):
    tester = PipelineNodeTester(
        embedding_provider=_FakeEmbeddingProvider(),
        index=_FakeIndex(),
    )
    source = _write_markdown(tmp_path / "policy.md")

    validation = tester.run(stage="validate", file_path=source)
    parsed = tester.run(stage="parse", file_path=source)
    chunked = tester.run(stage="chunk", file_path=source)
    embedded = tester.run(stage="embed", file_path=source)
    indexed = tester.run(stage="index", file_path=source)

    assert validation.summary["detected_content_type"] == "markdown"
    assert parsed.summary["normalization"] == "completed"
    assert parsed.summary["block_count"] == 4
    assert chunked.summary["child_chunk_count"] >= 1
    assert embedded.summary["dimensions"] == 4
    assert embedded.preview[0]["values"] == [0.5, 0.5, 0.5, 0.5]
    assert indexed.summary["mode"] == "non_destructive_readiness_check"
    assert indexed.summary["index_child_chunk_count"] == 15
