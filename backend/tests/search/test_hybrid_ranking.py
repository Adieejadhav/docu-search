from __future__ import annotations

from app.integrations.embeddings import EmbeddingProvider
from app.repositories import PgVectorChunkIndex


def test_hybrid_ranking_uses_vector_score_when_there_are_no_lexical_hits():
    index = PgVectorChunkIndex(
        database_url="postgresql://example/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )

    rows = index._merge_and_rerank_rows(
        query="satellite exception",
        vector_rows=[
            _row(
                child_id="child-1",
                vector_score=0.42,
                lexical_score=0.0,
            )
        ],
        lexical_rows=[],
        top_k=1,
    )

    assert rows[0]["score"] == 0.42
    assert rows[0]["vector_rank"] == 1
    assert rows[0]["lexical_rank"] is None


def test_hybrid_ranking_merges_duplicate_candidates_and_applies_weights():
    index = PgVectorChunkIndex(
        database_url="postgresql://example/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )

    rows = index._merge_and_rerank_rows(
        query="satellite exceptions",
        vector_rows=[
            _row(
                child_id="child-1",
                vector_score=0.70,
                lexical_score=0.01,
                child_text="satellite exception context",
            )
        ],
        lexical_rows=[
            _row(
                child_id="child-1",
                vector_score=0.60,
                lexical_score=0.20,
                child_text="satellite exception context",
            )
        ],
        top_k=1,
    )

    assert len(rows) == 1
    assert rows[0]["vector_score"] == 0.70
    assert rows[0]["lexical_score"] == 0.20
    assert rows[0]["vector_rank"] == 1
    assert rows[0]["lexical_rank"] == 1
    assert rows[0]["score"] == 0.814


def test_hybrid_ranking_uses_score_vector_and_vector_rank_for_ordering():
    index = PgVectorChunkIndex(
        database_url="postgresql://example/db",
        embedding_provider=_FakeEmbeddingProvider(),
    )

    rows = index._merge_and_rerank_rows(
        query="policy",
        vector_rows=[
            _row(child_id="child-1", vector_score=0.80, lexical_score=0.0),
            _row(child_id="child-2", vector_score=0.70, lexical_score=0.0),
        ],
        lexical_rows=[],
        top_k=2,
    )

    assert [row["child_id"] for row in rows] == ["child-1", "child-2"]


class _FakeEmbeddingProvider(EmbeddingProvider):
    @property
    def name(self) -> str:
        return "fake-embedding"

    @property
    def dimensions(self) -> int:
        return 3

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0, 0.0, 1.0] for _ in texts]


def _row(
    *,
    child_id: str,
    vector_score: float,
    lexical_score: float,
    child_text: str = "policy text",
) -> dict:
    return {
        "child_id": child_id,
        "child_json": {
            "id": child_id,
            "text": child_text,
        },
        "parent_json": {
            "id": f"parent-{child_id}",
            "text": "parent policy context",
        },
        "file_name": "policy.md",
        "file_type": "md",
        "vector_score": vector_score,
        "lexical_score": lexical_score,
    }
