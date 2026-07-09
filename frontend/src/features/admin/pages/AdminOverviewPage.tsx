import { type ReactNode, useEffect, useState } from "react";
import { useAppData } from "../../../app/AppDataContext";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { getAdminOverview } from "../../../services/api";
import type {
  AdminOverviewRecentJob,
  AdminOverviewRecentTrace,
  AdminOverviewResponse,
} from "../../../services/types";
import { BlueprintPage } from "../AdminBlueprintPrimitives";

export function AdminOverviewPage() {
  const { setError } = useAppData();
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);

  useEffect(() => {
    void refreshAdminOverview();
  }, []);

  async function refreshAdminOverview() {
    setError(null);
    try {
      setOverview(await getAdminOverview());
    } catch (error) {
      setError(messageFromError(error));
    }
  }

  const health = overview?.health;
  const index = overview?.index;
  const risk = overview?.risk;
  const jobs = overview?.ingestion_jobs;

  return (
    <BlueprintPage>
      <div className="ops-overview-page">
      <section className="ops-hero-grid" aria-label="Operational summary">
        <OverviewHeroCard
          label="System Health"
          value={health ? statusLabel(health.status) : "-"}
          description={health ? `DB ${statusLabel(health.database_status)} | ${shortModelName(health.llm_model)}` : "API, LLM, DB"}
          status={health?.status === "ok" ? "Healthy" : "Attention"}
          tone={health?.status === "ok" ? "ok" : "warn"}
        />
        <OverviewHeroCard
          label="Index Readiness"
          value={formatPercent(index?.readiness_percent)}
          description={`${formatMetric(index?.vector_count)} / ${formatMetric(index?.child_chunk_count)} vectors indexed`}
          status={indexStatus(index?.readiness_percent, index?.child_chunk_count)}
          tone="info"
        />
        <OverviewHeroCard
          label="Production Risk"
          value={risk ? `${risk.warning_count} warnings` : "-"}
          description={risk?.reasons[0] ?? "No active warnings"}
          status={risk?.status === "ok" ? "Clear" : "Attention"}
          tone={risk?.status === "ok" ? "ok" : "warn"}
        />
      </section>

      <section className="ops-content-grid">
        <OverviewPanel
          className="ops-panel-full"
          description="Latest RAG requests recorded by the backend trace store"
          title="Recent Query Traces"
        >
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Status</th>
                  <th>Chunks</th>
                  <th>Latency</th>
                  <th>Model</th>
                  <th>Time</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {overview?.recent_traces.length ? (
                  overview.recent_traces.map((trace) => (
                    <TraceRow key={trace.id} trace={trace} />
                  ))
                ) : (
                  <EmptyRow colSpan={7} message="No query traces yet." />
                )}
              </tbody>
            </table>
          </div>
        </OverviewPanel>

        <OverviewPanel
          className="ops-panel-full"
          description={jobs?.last_completed_at ? `Last completed ${formatDateTime(jobs.last_completed_at)}` : "Latest ingestion and indexing work"}
          title="Active Pipeline Jobs"
        >
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Files</th>
                  <th>Parsed docs</th>
                  <th>Indexed chunks</th>
                  <th>Failures</th>
                  <th>Duration</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {overview?.recent_jobs.length ? (
                  overview.recent_jobs.map((job) => (
                    <PipelineJobRow job={job} key={job.id} />
                  ))
                ) : (
                  <EmptyRow colSpan={8} message="No ingestion jobs yet." />
                )}
              </tbody>
            </table>
          </div>
        </OverviewPanel>
      </section>
      </div>
    </BlueprintPage>
  );
}

function OverviewHeroCard({
  description,
  label,
  status,
  tone,
  value,
}: {
  description: string;
  label: string;
  status: string;
  tone: "info" | "ok" | "violet" | "warn";
  value: string;
}) {
  return (
    <article className={`ops-hero-card ${tone}`}>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{description}</small>
      </div>
      <em>{status}</em>
    </article>
  );
}

function OverviewPanel({
  children,
  className,
  description,
  title,
}: {
  children: ReactNode;
  className?: string;
  description: string;
  title: string;
}) {
  return (
    <section className={["ops-panel", className].filter(Boolean).join(" ")}>
      <header>
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </header>
      <div className="ops-panel-body">{children}</div>
    </section>
  );
}

function TraceRow({ trace }: { trace: AdminOverviewRecentTrace }) {
  return (
    <tr>
      <td>{trace.query}</td>
      <td>
        <span className="overview-table-pill ok">{statusLabel(trace.status)}</span>
      </td>
      <td>
        <span className="overview-table-pill chunks">{formatMetric(trace.result_count)}</span>
      </td>
      <td>
        <span className="overview-table-pill latency">{formatDuration(trace.total_ms)}</span>
      </td>
      <td>
        <span className="overview-table-pill model">{shortModelName(trace.llm_model)}</span>
      </td>
      <td>{formatDateTime(trace.created_at)}</td>
      <td><button type="button">View</button></td>
    </tr>
  );
}

function PipelineJobRow({ job }: { job: AdminOverviewRecentJob }) {
  return (
    <tr>
      <td>
        <span className="overview-table-pill source">{titleCase(job.source_kind)}</span>
      </td>
      <td>
        <span className={`overview-table-pill ${job.status === "completed" ? "ok" : "warn"}`}>
          {statusLabel(job.status)}
        </span>
      </td>
      <td>
        <span className="overview-table-pill files">{formatMetric(job.file_count)}</span>
      </td>
      <td>
        <span className="overview-table-pill parent">{formatMetric(job.parsed_document_count)}</span>
      </td>
      <td>
        <span className="overview-table-pill chunks">{formatMetric(job.indexed_child_count)}</span>
      </td>
      <td>
        <span className={`overview-table-pill ${job.failure_count ? "danger" : "muted"}`}>
          {formatMetric(job.failure_count)}
        </span>
      </td>
      <td>
        <span className="overview-table-pill latency">{formatDuration(job.duration_ms)}</span>
      </td>
      <td>{formatDateTime(job.updated_at)}</td>
    </tr>
  );
}

function EmptyRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td colSpan={colSpan}>{message}</td>
    </tr>
  );
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}

function formatPercent(value: number | null | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 10) / 10}%` : "-";
}

function formatDuration(value: number | null | undefined): string {
  if (typeof value !== "number") return "-";
  if (value >= 1000) {
    const seconds = value / 1000;
    return `${seconds >= 10 ? Math.round(seconds) : seconds.toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}

function indexStatus(readinessPercent: number | null | undefined, childChunkCount: number | null | undefined): string {
  if (typeof readinessPercent !== "number") return "Loading";
  if (!childChunkCount) return "Empty";
  return readinessPercent >= 100 ? "Ready" : "Syncing";
}

function shortModelName(value: string | null | undefined): string {
  const trimmed = (value ?? "").trim();
  if (!trimmed) return "-";

  const pathParts = trimmed.split(/[\\/]/).filter(Boolean);
  return pathParts.at(-1) ?? trimmed;
}

function statusLabel(value: string): string {
  if (value.toLowerCase() === "ok") return "OK";
  return titleCase(value);
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\w\S*/g, (word) => `${word.charAt(0).toUpperCase()}${word.slice(1).toLowerCase()}`);
}
