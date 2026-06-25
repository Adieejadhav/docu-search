import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  Activity,
  Bot,
  CalendarCheck,
  CalendarDays,
  CalendarRange,
  Database,
  FileText,
  HeartPulse,
  Layers3,
  RefreshCw,
  Search,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { asText, messageFromError, summarizeDocuments } from "../../../lib/format";
import { getDocuments, listIngestionJobs, listRagTraces } from "../../../services/api";
import type {
  AdminOverviewResponse,
  DocumentSummary,
  IngestionJob,
  RagTraceSummary,
} from "../../../services/types";

const DOCUMENT_PAGE_SIZE = 500;
const ADMIN_PAGE_SIZE = 100;

export function AdminOverviewPage() {
  const { documents, health, setError } = useAppData();
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [isLoadingOverview, setLoadingOverview] = useState(false);
  const fallbackStats = summarizeDocuments(documents?.documents ?? []);
  const documentCount = overview?.document_count ?? documents?.total;
  const parentChunkCount =
    overview?.parent_chunk_count ?? (documents ? fallbackStats.parentChunks : undefined);
  const childChunkCount =
    overview?.child_chunk_count ?? (documents ? fallbackStats.childChunks : undefined);
  const vectorCount = overview?.vector_count;
  const queries = overview?.queries;
  const jobs = overview?.ingestion_jobs;
  const embeddingModel = asText(health?.embedding.details.model);
  const llmModel = asText(health?.llm.details.model);

  useEffect(() => {
    void refreshAdminOverview();
  }, []);

  async function refreshAdminOverview() {
    setLoadingOverview(true);
    setError(null);
    try {
      setOverview(await loadOverviewSnapshot());
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setLoadingOverview(false);
    }
  }

  return (
    <>
      <section className="overview-toolbar">
        <div>
          <p className="eyebrow">Database Snapshot</p>
          <h2>Admin overview</h2>
        </div>
        <button
          className="secondary-button button-small"
          disabled={isLoadingOverview}
          onClick={() => void refreshAdminOverview()}
          type="button"
        >
          <RefreshCw className={isLoadingOverview ? "animate-spin" : ""} size={14} />
          Refresh
        </button>
      </section>

      <section className="overview-metric-grid" aria-label="System overview">
        <OverviewMetricCard
          icon={<HeartPulse size={18} />}
          label="API"
          value={health?.status ?? "loading"}
          tone={health?.status}
        />
        <OverviewMetricCard
          icon={<FileText size={18} />}
          label="Total docs"
          value={formatMetric(documentCount)}
          detail="Indexed source documents"
          tone="cyan"
        />
        <OverviewMetricCard
          icon={<Layers3 size={18} />}
          label="Parent chunks"
          value={formatMetric(parentChunkCount)}
          detail="Top-level retrieval groups"
          tone="violet"
        />
        <OverviewMetricCard
          icon={<Database size={18} />}
          label="Child chunks"
          value={formatMetric(childChunkCount)}
          detail="Searchable chunk records"
          tone="accent"
        />
        <OverviewMetricCard
          icon={<Sparkles size={18} />}
          label="Total vectors"
          value={formatMetric(vectorCount)}
          detail="Stored embeddings"
          tone="emerald"
        />
        <OverviewMetricCard
          icon={<Search size={18} />}
          label="Total queries"
          value={formatMetric(queries?.total)}
          detail="All RAG query traces"
          tone="slate"
        />
        <OverviewMetricCard
          icon={<CalendarCheck size={18} />}
          label="Queries today"
          value={formatMetric(queries?.today)}
          detail="Since start of day"
          tone="cyan"
        />
        <OverviewMetricCard
          icon={<CalendarDays size={18} />}
          label="Queries this month"
          value={formatMetric(queries?.month)}
          detail="Current calendar month"
          tone="violet"
        />
        <OverviewMetricCard
          icon={<CalendarRange size={18} />}
          label="Queries this year"
          value={formatMetric(queries?.year)}
          detail="Current calendar year"
          tone="amber"
        />
        <OverviewMetricCard
          icon={<Workflow size={18} />}
          label="Ingestion jobs done"
          value={formatMetric(jobs?.completed)}
          detail={
            jobs
              ? `${formatMetric(jobs.total)} total / ${formatMetric(jobs.failed)} failed`
              : "Completed jobs"
          }
          tone="emerald"
        />
        <OverviewMetricCard
          icon={<Activity size={18} />}
          label="Embedding model"
          value={shortModelName(embeddingModel) || "loading"}
          detail={`${asText(health?.embedding.details.dimensions) || "-"} dimensions`}
          tone="rose"
        />
        <OverviewMetricCard
          icon={<Bot size={18} />}
          label="LLM"
          value={shortModelName(llmModel) || "loading"}
          detail={asText(health?.llm.details.host)}
          tone="slate"
        />
      </section>
    </>
  );
}

type OverviewMetricTone =
  | "accent"
  | "amber"
  | "cyan"
  | "degraded"
  | "emerald"
  | "ok"
  | "rose"
  | "slate"
  | "violet";

function OverviewMetricCard({
  detail,
  icon,
  label,
  tone = "accent",
  value,
}: {
  detail?: string;
  icon: ReactNode;
  label: string;
  tone?: OverviewMetricTone;
  value: string;
}) {
  return (
    <article
      className={["overview-metric-card", tone].filter(Boolean).join(" ")}
      title={[label, value, detail].filter(Boolean).join(" · ")}
    >
      <div className="overview-metric-icon">{icon}</div>
      <div className="overview-metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        {detail && <small>{detail}</small>}
      </div>
    </article>
  );
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "loading";
}

function shortModelName(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";

  const pathParts = trimmed.split(/[\\/]/).filter(Boolean);
  return pathParts.at(-1) ?? trimmed;
}

async function loadOverviewSnapshot(): Promise<AdminOverviewResponse> {
  const [documents, traces, jobs] = await Promise.all([
    loadAllDocuments(),
    loadAllTraces(),
    loadAllIngestionJobs(),
  ]);
  const chunkStats = summarizeDocuments(documents.documents);
  const queryCounts = summarizeQueries(traces.traces, traces.total);
  const jobCounts = summarizeJobs(jobs.jobs, jobs.total);

  return {
    document_count: documents.total,
    parent_chunk_count: chunkStats.parentChunks,
    child_chunk_count: chunkStats.childChunks,
    vector_count: chunkStats.childChunks,
    queries: queryCounts,
    ingestion_jobs: jobCounts,
  };
}

async function loadAllDocuments(): Promise<{
  total: number;
  documents: DocumentSummary[];
}> {
  const documents: DocumentSummary[] = [];
  let total = 0;
  let offset = 0;

  do {
    const page = await getDocuments({ limit: DOCUMENT_PAGE_SIZE, offset });
    total = page.total;
    documents.push(...page.documents);
    offset += page.documents.length;
  } while (documents.length < total && offset > 0);

  return { total, documents };
}

async function loadAllTraces(): Promise<{
  total: number;
  traces: RagTraceSummary[];
}> {
  const traces: RagTraceSummary[] = [];
  let total = 0;
  let offset = 0;

  do {
    const page = await listRagTraces({ limit: ADMIN_PAGE_SIZE, offset });
    total = page.total;
    traces.push(...page.traces);
    offset += page.traces.length;
  } while (traces.length < total && offset > 0);

  return { total, traces };
}

async function loadAllIngestionJobs(): Promise<{
  total: number;
  jobs: IngestionJob[];
}> {
  const jobs: IngestionJob[] = [];
  let total = 0;
  let offset = 0;

  do {
    const page = await listIngestionJobs({ limit: ADMIN_PAGE_SIZE, offset });
    total = page.total;
    jobs.push(...page.jobs);
    offset += page.jobs.length;
  } while (jobs.length < total && offset > 0);

  return { total, jobs };
}

function summarizeQueries(
  traces: RagTraceSummary[],
  total: number,
): AdminOverviewResponse["queries"] {
  const now = new Date();
  const dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const yearStart = new Date(now.getFullYear(), 0, 1);

  return {
    total,
    today: traces.filter((trace) => isOnOrAfter(trace.created_at, dayStart)).length,
    month: traces.filter((trace) => isOnOrAfter(trace.created_at, monthStart)).length,
    year: traces.filter((trace) => isOnOrAfter(trace.created_at, yearStart)).length,
  };
}

function summarizeJobs(
  jobs: IngestionJob[],
  total: number,
): AdminOverviewResponse["ingestion_jobs"] {
  return {
    total,
    queued: jobs.filter((job) => job.status === "queued").length,
    running: jobs.filter((job) => job.status === "running").length,
    completed: jobs.filter((job) => job.status === "completed").length,
    failed: jobs.filter((job) => job.status === "failed").length,
  };
}

function isOnOrAfter(value: string, start: Date): boolean {
  const date = new Date(value);
  return !Number.isNaN(date.getTime()) && date >= start;
}
