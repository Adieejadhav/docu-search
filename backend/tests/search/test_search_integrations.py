from __future__ import annotations

from app.integrations.search import LexicalSearch, PgVectorSearch


def test_pgvector_search_preserves_filter_params_and_order():
    connection = _FakeConnection()

    rows = PgVectorSearch().search_rows(
        connection=connection,
        query_vector_text="[0,1,0]",
        query="satellite policy",
        top_k=5,
        metadata_filters={
            "file_name": "policy.md",
            "file_type": "md",
            "document_id": "doc-1",
        },
    )

    assert rows == [{"child_id": "child-1"}]
    assert "d.file_name = %s" in connection.sql
    assert "d.file_type = %s" in connection.sql
    assert "cc.document_id = %s" in connection.sql
    assert connection.params == [
        "[0,1,0]",
        "satellite policy",
        "policy.md",
        "md",
        "doc-1",
        "[0,1,0]",
        5,
    ]


def test_lexical_search_preserves_query_params_filters_and_ordering():
    connection = _FakeConnection()

    rows = LexicalSearch().search_rows(
        connection=connection,
        query_vector_text="[0,1,0]",
        query="satellite policy",
        top_k=5,
        metadata_filters={"document_id": "doc-1"},
    )

    assert rows == [{"child_id": "child-1"}]
    assert "websearch_to_tsquery('english', %s)" in connection.sql
    assert "cc.document_id = %s" in connection.sql
    assert "ORDER BY lexical_score DESC, vector_score DESC" in connection.sql
    assert connection.params == [
        "[0,1,0]",
        "satellite policy",
        "satellite policy",
        "satellite policy",
        "satellite policy",
        "doc-1",
        5,
    ]


class _FakeConnection:
    def __init__(self) -> None:
        self.sql = ""
        self.params = []

    def execute(self, sql: str, params: list):
        self.sql = sql
        self.params = params
        return [{"child_id": "child-1"}]
