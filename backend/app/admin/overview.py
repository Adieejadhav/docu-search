from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.db import check_database_health
from app.db.connection import connect_postgres
from app.embeddings import EmbeddingProvider
from app.indexing import PgVectorChunkIndex
from app.ingestion.jobs import IngestionJobRecord, IngestionJobStore
from app.llm import OllamaChatClient
from app.rag.traces import RagTraceRecord, RagTraceStore
from app.schemas import (
    AdminOverviewHealth,
    AdminOverviewIndexStats,
    AdminOverviewIngestionJobs,
    AdminOverviewQueryCounts,
    AdminOverviewRecentJob,
    AdminOverviewRecentTrace,
    AdminOverviewResponse,
    AdminOverviewRisk,
)

RECENT_OVERVIEW_LIMIT = 5


class AdminOverviewService:
    def __init__(
        self,
        *,
        database_url: str,
        index: PgVectorChunkIndex,
        embedding_provider: EmbeddingProvider,
        llm_client: OllamaChatClient,
    ) -> None:
        self.database_url = database_url
        self.index = index
        self.embedding_provider = embedding_provider
        self.llm_client = llm_client

    def build(self) -> AdminOverviewResponse:
        index_stats = self.index.stats()
        database_health = check_database_health(self.database_url)

        trace_store = RagTraceStore(database_url=self.database_url)
        job_store = IngestionJobStore(database_url=self.database_url)
        trace_store.initialize()
        job_store.initialize()

        with connect_postgres(self.database_url) as connection:
            vector_count = count_child_embeddings(connection)
            queries = query_count_summary(connection)
            ingestion_jobs = ingestion_job_summary(connection)

        index = AdminOverviewIndexStats(
            document_count=index_stats.document_count,
            parent_chunk_count=index_stats.parent_chunk_count,
            child_chunk_count=index_stats.child_chunk_count,
            vector_count=vector_count,
            readiness_percent=readiness_percent(
                child_chunk_count=index_stats.child_chunk_count,
                vector_count=vector_count,
            ),
        )
        recent_traces = [
            recent_trace_response(trace)
            for trace in trace_store.list_traces(limit=RECENT_OVERVIEW_LIMIT).traces
        ]
        recent_jobs = [
            recent_job_response(job)
            for job in job_store.list_jobs(limit=RECENT_OVERVIEW_LIMIT).jobs
        ]

        return AdminOverviewResponse(
            health=AdminOverviewHealth(
                status="ok" if database_health.ok else "degraded",
                database_status="ok" if database_health.ok else "degraded",
                embedding_model=embedding_model_name(self.embedding_provider),
                llm_model=self.llm_client.model,
                llm_host=self.llm_client.host,
            ),
            index=index,
            queries=queries,
            ingestion_jobs=ingestion_jobs,
            risk=overview_risk(
                database_ok=database_health.ok,
                index=index,
                ingestion_jobs=ingestion_jobs,
            ),
            recent_traces=recent_traces,
            recent_jobs=recent_jobs,
        )


def count_child_embeddings(connection: Any) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM child_embeddings",
    ).fetchone()
    return int(row["count"])


def embedding_model_name(provider: EmbeddingProvider) -> str:
    return str(getattr(provider, "model", provider.name))


def query_count_summary(connection: Any) -> AdminOverviewQueryCounts:
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
            ) AS year,
            AVG(total_ms) AS avg_latency_ms,
            PERCENTILE_CONT(0.95) WITHIN GROUP (
                ORDER BY total_ms
            ) AS p95_latency_ms
        FROM rag_traces
        """
    ).fetchone()

    return AdminOverviewQueryCounts(
        total=int(row["total"]),
        today=int(row["today"]),
        month=int(row["month"]),
        year=int(row["year"]),
        avg_latency_ms=rounded_float(row["avg_latency_ms"]),
        p95_latency_ms=rounded_float(row["p95_latency_ms"]),
    )


def ingestion_job_summary(connection: Any) -> AdminOverviewIngestionJobs:
    row = connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status = 'queued') AS queued,
            COUNT(*) FILTER (WHERE status = 'running') AS running,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed,
            MAX(completed_at) FILTER (
                WHERE status = 'completed'
            ) AS last_completed_at
        FROM ingestion_jobs
        """
    ).fetchone()

    return AdminOverviewIngestionJobs(
        total=int(row["total"]),
        queued=int(row["queued"]),
        running=int(row["running"]),
        completed=int(row["completed"]),
        failed=int(row["failed"]),
        last_completed_at=row["last_completed_at"],
    )


def readiness_percent(*, child_chunk_count: int, vector_count: int) -> float:
    if child_chunk_count <= 0:
        return 0.0
    return round(min(100.0, (vector_count / child_chunk_count) * 100), 2)


def overview_risk(
    *,
    database_ok: bool,
    index: AdminOverviewIndexStats,
    ingestion_jobs: AdminOverviewIngestionJobs,
) -> AdminOverviewRisk:
    reasons: list[str] = []
    if not database_ok:
        reasons.append("Database health is degraded")
    if index.document_count == 0:
        reasons.append("No documents are indexed")
    if index.vector_count < index.child_chunk_count:
        reasons.append("Some child chunks do not have vectors")
    if ingestion_jobs.failed > 0:
        reasons.append(f"{ingestion_jobs.failed} ingestion job(s) failed")

    return AdminOverviewRisk(
        status="attention" if reasons else "ok",
        warning_count=len(reasons),
        reasons=reasons,
    )


def recent_trace_response(trace: RagTraceRecord) -> AdminOverviewRecentTrace:
    return AdminOverviewRecentTrace(
        id=trace.id,
        query=trace.query,
        status="success",
        result_count=trace.result_count,
        retrieval_ms=trace.retrieval_ms,
        answer_ms=trace.answer_ms,
        total_ms=trace.total_ms,
        llm_model=trace.llm_model,
        created_at=trace.created_at,
    )


def recent_job_response(job: IngestionJobRecord) -> AdminOverviewRecentJob:
    return AdminOverviewRecentJob(
        id=job.id,
        status=job.status,
        source_kind=job.source_kind,
        file_count=job.file_count,
        parsed_document_count=job.parsed_document_count,
        indexed_child_count=job.indexed_child_count,
        failure_count=job.failure_count,
        duration_ms=job_duration_ms(job),
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


def job_duration_ms(job: IngestionJobRecord) -> float | None:
    total = job.timings_ms.get("total")
    if total is not None:
        return rounded_float(total)
    if job.started_at is None or job.completed_at is None:
        return None
    return round((job.completed_at - job.started_at).total_seconds() * 1000, 3)


def rounded_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    return round(float(value), 3)
