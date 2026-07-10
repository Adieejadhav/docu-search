"""
File: backend/app/integrations/search/pgvector_search.py
Purpose: Executes pgvector candidate retrieval queries.
"""

from __future__ import annotations

from typing import Any


class PgVectorSearch:
    """Runs vector-similarity candidate retrieval against PostgreSQL/pgvector."""

    def search_rows(
        self,
        *,
        connection: Any,
        query_vector_text: str,
        query: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        where_parts: list[str] = []
        filter_params: list[Any] = []

        for field_name in ("file_name", "file_type", "document_id"):
            if metadata_filters and field_name in metadata_filters:
                if field_name == "document_id":
                    where_parts.append("cc.document_id = %s")
                else:
                    where_parts.append(f"d.{field_name} = %s")
                filter_params.append(metadata_filters[field_name])

        where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        return list(
            connection.execute(
                f"""
                SELECT
                    cc.id AS child_id,
                    cc.chunk_json AS child_json,
                    pc.chunk_json AS parent_json,
                    d.file_name AS file_name,
                    d.file_type AS file_type,
                    1 - (ce.embedding <=> %s::vector) AS vector_score,
                    ts_rank_cd(
                        to_tsvector('english', cc.text || ' ' || pc.text || ' ' || d.file_name),
                        websearch_to_tsquery('english', %s)
                    ) AS lexical_score
                FROM child_chunks cc
                JOIN child_embeddings ce ON ce.child_chunk_id = cc.id
                JOIN parent_chunks pc ON pc.id = cc.parent_chunk_id
                JOIN documents d ON d.id = cc.document_id
                {where_clause}
                ORDER BY ce.embedding <=> %s::vector
                LIMIT %s
                """,
                [query_vector_text, query, *filter_params, query_vector_text, top_k],
            )
        )
