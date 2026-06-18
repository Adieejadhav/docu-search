from __future__ import annotations

from app.evaluation.runner import missing_terms
from app.indexing.pgvector_index import PgVectorChunkIndex


def test_missing_terms_handles_unicode_hyphens_and_plural_variants():
    answer = (
        "The Password rotation exception policy is P\u2011004. "
        "It covers the 14\u2011day satellite mode case, and a human dispatcher "
        "must confirm safety classification."
    )

    missing = missing_terms(
        answer,
        ["P-004", "14 days", "Human dispatchers", "safety classification"],
    )

    assert missing == []


def test_hybrid_rerank_promotes_lexical_procedure_candidate():
    index = PgVectorChunkIndex.__new__(PgVectorChunkIndex)
    vector_only_asset = {
        "child_id": "asset",
        "file_name": "09_aquila_nested_corpus.json",
        "file_type": "json",
        "child_json": {
            "text": 'Document: assets ["TX-028", "Gateway 28"]',
            "parent_path": ["$", "assets", "[27]"],
        },
        "parent_json": {
            "text": 'Document: assets ["TX-028", "Gateway 28"]',
            "parent_path": ["$", "assets", "[27]"],
        },
        "vector_score": 0.71,
        "lexical_score": 0.0,
    }
    procedure = {
        "child_id": "procedure",
        "file_name": "02_aquila_product_knowledge_base.md",
        "file_type": "md",
        "child_json": {
            "text": (
                "Normalize asset identifier. Example aliases: TX-0091, "
                "Transformer 91, TRF_91."
            ),
            "parent_path": ["Nested Procedure"],
        },
        "parent_json": {
            "text": (
                "Normalize asset identifier. Example aliases: TX-0091, "
                "Transformer 91, TRF_91."
            ),
            "parent_path": ["Nested Procedure"],
        },
        "vector_score": 0.66,
        "lexical_score": 0.08,
    }

    rows = index._merge_and_rerank_rows(
        query="How should asset aliases be normalized?",
        vector_rows=[vector_only_asset],
        lexical_rows=[procedure],
        top_k=2,
    )

    assert rows[0]["child_id"] == "procedure"
