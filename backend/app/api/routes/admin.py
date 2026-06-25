from __future__ import annotations

import os

from fastapi import APIRouter, Depends

from app.api.dependencies import get_chunk_index, get_database_url
from app.api.middleware import metrics_snapshot
from app.core.exceptions import RetrievalError
from app.db.connection import connect_postgres
from app.indexing import PgVectorChunkIndex
from app.ingestion.jobs import IngestionJobStore
from app.rag.traces import RagTraceStore
from app.schemas import (
    AdminClearIndexRequest,
    AdminClearIndexResponse,
    AdminOverviewIngestionJobs,
    AdminOverviewQueryCounts,
    AdminOverviewResponse,
)

router = APIRouter()


@router.post("/index/clear", response_model=AdminClearIndexResponse)
def clear_index(
    request: AdminClearIndexRequest,
    index: PgVectorChunkIndex = Depends(get_chunk_index),
) -> AdminClearIndexResponse:
    if not request.confirm:
        raise RetrievalError(
            "Index clear requires confirm=true",
            code="INDEX_CLEAR_NOT_CONFIRMED",
        )

    index.clear()
    stats = index.stats()
    return AdminClearIndexResponse(
        status="cleared",
        document_count=stats.document_count,
        parent_chunk_count=stats.parent_chunk_count,
        child_chunk_count=stats.child_chunk_count,
    )


@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    index: PgVectorChunkIndex = Depends(get_chunk_index),
    database_url: str = Depends(get_database_url),
) -> AdminOverviewResponse:
    """
    Returns exact database-backed counts for the admin overview dashboard.
    """

    index_stats = index.stats()
    RagTraceStore(database_url=database_url).initialize()
    IngestionJobStore(database_url=database_url).initialize()

    with connect_postgres(database_url) as connection:
        vector_count = count_rows(connection, "child_embeddings")
        query_counts = query_count_summary(connection)
        ingestion_jobs = ingestion_job_summary(connection)

    return AdminOverviewResponse(
        document_count=index_stats.document_count,
        parent_chunk_count=index_stats.parent_chunk_count,
        child_chunk_count=index_stats.child_chunk_count,
        vector_count=vector_count,
        queries=query_counts,
        ingestion_jobs=ingestion_jobs,
    )


@router.get("/metrics")
def get_api_metrics() -> dict:
    return metrics_snapshot()


@router.get("/auth/status")
def get_admin_auth_status() -> dict:
    return {
        "admin_token_required": bool(os.getenv("ADMIN_API_TOKEN")),
    }


def count_rows(connection, table_name: str) -> int:
    if table_name not in {"child_embeddings"}:
        raise RetrievalError(
            "Unsupported overview count table",
            code="UNSUPPORTED_OVERVIEW_COUNT_TABLE",
            details={"table_name": table_name},
        )

    row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
    return int(row["count"])


def query_count_summary(connection) -> AdminOverviewQueryCounts:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (
                WHERE created_at >= date_trunc('day', NOW())
            ) AS today,
            COUNT(*) FILTER (
                WHERE created_at >= date_trunc('month', NOW())
            ) AS month,
            COUNT(*) FILTER (
                WHERE created_at >= date_trunc('year', NOW())
            ) AS year
        FROM rag_traces
        """
    ).fetchone()

    return AdminOverviewQueryCounts(
        total=int(row["total"]),
        today=int(row["today"]),
        month=int(row["month"]),
        year=int(row["year"]),
    )


def ingestion_job_summary(connection) -> AdminOverviewIngestionJobs:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'queued') AS queued,
            COUNT(*) FILTER (WHERE status = 'running') AS running,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed
        FROM ingestion_jobs
        """
    ).fetchone()

    return AdminOverviewIngestionJobs(
        total=int(row["total"]),
        queued=int(row["queued"]),
        running=int(row["running"]),
        completed=int(row["completed"]),
        failed=int(row["failed"]),
    )
