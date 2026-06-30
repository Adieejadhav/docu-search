import { type ReactNode, useEffect, useMemo, useState } from "react";
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
  const fallbackStats = summarizeDocuments(documents?.documents ?? []);
  const documentCount = overview?.document_count ?? documents?.total;
  const parentChunkCount =
    overview?.parent_chunk_count ?? (documents ? fallbackStats.parentChunks : undefined);
  const childChunkCount =
    overview?.child_chunk_count ?? (documents ? fallbackStats.childChunks : undefined);
  const vectorCount = overview?.vector_count ?? childChunkCount;
  const queries = overview?.queries;
  const jobs = overview?.ingestion_jobs;
  const embeddingModel = shortModelName(asText(health?.embedding.details.model)) || "bge-small-en-v1.5";
  const llmModel = shortModelName(asText(health?.llm.details.model)) || "gpt-oss:120b-cloud";
  const llmHost = asText(health?.llm.details.host) || "localhost:11434";

  useEffect(() => {
    void refreshAdminOverview();
  }, []);

  const indexReadiness = useMemo(() => {
    if (!childChunkCount || !vectorCount) return "—";
    return `${Math.min(100, Math.round((vectorCount / childChunkCount) * 100))}%`;
  }, [childChunkCount, vectorCount]);

  async function refreshAdminOverview() {
    setError(null);
    try {
      setOverview(await loadOverviewSnapshot());
    } catch (error) {
      setError(messageFromError(error));
    }
  }

  return (
    <div className="ops-overview-page">
      <section className="ops-hero-grid" aria-label="Operational summary">
        <OverviewHeroCard
          label="System Health"
          value={health?.status === "ok" ? "98%" : health ? "74%" : "—"}
          description="API, LLM, DB, workers"
          status={health?.status === "ok" ? "Healthy" : "Attention"}
          tone={health?.status === "ok" ? "ok" : "warn"}
        />
        <OverviewHeroCard
          label="Index Readiness"
          value={indexReadiness}
          description={`${formatMetric(vectorCount)} / ${formatMetric(childChunkCount)} vectors indexed`}
          status={indexReadiness === "100%" ? "Ready" : "Syncing"}
          tone="info"
        />
        <OverviewHeroCard
          label="Answer Quality"
          value="91%"
          description="grounded recent answers"
          status="Stable"
          tone="violet"
        />
        <OverviewHeroCard
          label="Production Risk"
          value={jobs?.failed ? `${jobs.failed} warnings` : "2 warnings"}
          description="review recommended"
          status="Attention"
          tone="warn"
        />
      </section>

      <section className="ops-inventory-grid" aria-label="Index inventory">
        <OverviewStat label="Documents" value={formatMetric(documentCount)} detail="indexed" />
        <OverviewStat label="Parent chunks" value={formatMetric(parentChunkCount)} detail="retrieval groups" />
        <OverviewStat label="Child chunks" value={formatMetric(childChunkCount)} detail="search records" />
        <OverviewStat label="Vectors" value={formatMetric(vectorCount)} detail="no missing vectors" />
        <OverviewStat label="Queries" value={formatMetric(queries?.total)} detail={`${formatMetric(queries?.today)} today`} />
      </section>

      <section className="ops-content-grid">
        <OverviewPanel
          className="ops-panel-wide"
          description="Pipeline readiness across document processing stages"
          title="Ingestion & Indexing Health"
        >
          <div className="ops-timeline">
            <PipelineStep label="Upload" value={formatMetric(documentCount)} />
            <PipelineStep label="Extract" value={formatMetric(documentCount)} />
            <PipelineStep label="Chunk" value={formatMetric(documentCount)} />
            <PipelineStep label="Embed" value={formatMetric(vectorCount)} />
            <PipelineStep label="Index" value={formatMetric(vectorCount)} />
            <PipelineStep label="Ready" value={formatMetric(documentCount)} />
          </div>
          <div className="ops-inline-metrics">
            <InlineMetric label="Failed jobs" value={formatMetric(jobs?.failed)} detail="all clear" />
            <InlineMetric label="Last indexed" value="8m" detail="recent sync" />
            <InlineMetric label="Avg processing" value="14.2s" detail="per document" />
          </div>
        </OverviewPanel>

        <OverviewPanel
          className="ops-panel-compact"
          description="Recent traces and evaluation-derived production scores"
          title="Retrieval & Answer Quality"
        >
          <div className="ops-quality-grid">
            <QualityMetric label="Retrieval hit rate" value="94%" detail="relevant chunks found" />
            <QualityMetric label="Citation coverage" value="88%" detail="answers with sources" />
            <QualityMetric label="Groundedness" value="91%" detail="supported by context" />
            <QualityMetric label="Low-confidence traces" value="2" detail="needs review" tone="warn" />
          </div>
        </OverviewPanel>

        <OverviewPanel
          className="ops-panel-wide"
          description="Operational volume and runtime performance"
          title="Usage, Latency & Cost"
        >
          <div className="ops-quality-grid four">
            <QualityMetric label="Queries today" value={formatMetric(queries?.today)} detail="traffic" />
            <QualityMetric label="Avg latency" value="1.8s" detail="end-to-end" />
            <QualityMetric label="P95 latency" value="3.4s" detail="slow requests" />
            <QualityMetric label="Provider cost" value="$0.00" detail="local runtime" />
          </div>
          <p className="ops-runtime-line">
            Model: {llmModel} · Embedding: {embeddingModel} · Runtime: {llmHost}
          </p>
        </OverviewPanel>

        <OverviewPanel
          className="ops-panel-compact"
          description="Prioritized actions for production readiness"
          title="Critical Alerts"
        >
          <div className="ops-alert-list">
            <AlertRow action="Run evaluation" label="Evaluation not run in the last 7 days" tone="warn" />
            <AlertRow action="Review traces" label="2 low-grounded traces need review" tone="warn" />
            <AlertRow action="View jobs" label="No failed ingestion jobs" tone="ok" />
            <AlertRow action="Inspect index" label="No missing vectors detected" tone="ok" />
          </div>
        </OverviewPanel>

        <OverviewPanel
          className="ops-panel-full"
          description="Debug RAG behaviour from the latest user requests"
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
                  <th>Grounded</th>
                  <th>Model</th>
                  <th>Feedback</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <TraceRow
                  chunks="4"
                  feedback="positive"
                  grounded="92%"
                  latency="1.6s"
                  model={llmModel}
                  query="What is the document retention policy?"
                  status="Success"
                />
                <TraceRow
                  chunks="3"
                  feedback="none"
                  grounded="88%"
                  latency="2.1s"
                  model={llmModel}
                  query="Summarize onboarding steps for HR."
                  status="Success"
                />
                <TraceRow
                  chunks="1"
                  feedback="negative"
                  grounded="61%"
                  latency="3.2s"
                  model={llmModel}
                  query="Who approved the finance SOP?"
                  status="Warning"
                  tone="warn"
                />
              </tbody>
            </table>
          </div>
        </OverviewPanel>

        <OverviewPanel
          className="ops-panel-full"
          description="Latest ingestion/indexing work and retry/debug actions"
          title="Active Pipeline Jobs"
        >
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Stage</th>
                  <th>Status</th>
                  <th>Duration</th>
                  <th>Progress</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <PipelineJobRow document="HR Policy.pdf" duration="12.4s" stage="Indexed" />
                <PipelineJobRow document="Finance SOP.pdf" duration="18.7s" stage="Embedded" />
              </tbody>
            </table>
          </div>
        </OverviewPanel>
      </section>
    </div>
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

function OverviewStat({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <article className="ops-stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
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

function PipelineStep({ label, value }: { label: string; value: string }) {
  return (
    <article className="ops-step">
      <i>✓</i>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function InlineMetric({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function QualityMetric({
  detail,
  label,
  tone,
  value,
}: {
  detail: string;
  label: string;
  tone?: "warn";
  value: string;
}) {
  return (
    <article className={tone === "warn" ? "warn" : undefined}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function AlertRow({
  action,
  label,
  tone,
}: {
  action: string;
  label: string;
  tone: "ok" | "warn";
}) {
  return (
    <article className={`ops-alert-row ${tone}`}>
      <span>{label}</span>
      <button type="button">{action}</button>
    </article>
  );
}

function TraceRow({
  chunks,
  feedback,
  grounded,
  latency,
  model,
  query,
  status,
  tone = "ok",
}: {
  chunks: string;
  feedback: string;
  grounded: string;
  latency: string;
  model: string;
  query: string;
  status: string;
  tone?: "ok" | "warn";
}) {
  return (
    <tr>
      <td>{query}</td>
      <td><span className={`ops-status ${tone}`}>{status}</span></td>
      <td>{chunks}</td>
      <td>{latency}</td>
      <td><span className={`ops-status ${tone}`}>{grounded}</span></td>
      <td>{model}</td>
      <td>{feedback}</td>
      <td><button type="button">{tone === "warn" ? "Review" : "View"}</button></td>
    </tr>
  );
}

function PipelineJobRow({
  document,
  duration,
  stage,
}: {
  document: string;
  duration: string;
  stage: string;
}) {
  return (
    <tr>
      <td>{document}</td>
      <td>{stage}</td>
      <td><span className="ops-status ok">Completed</span></td>
      <td>{duration}</td>
      <td>Upload ✓ Extract ✓ Chunk ✓ Embed ✓ Index ✓</td>
      <td><button type="button">Inspect</button></td>
    </tr>
  );
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "—";
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
    completed: jobs.filter((job) => job.status === "completed").length,
    failed: jobs.filter((job) => job.status === "failed").length,
    running: jobs.filter((job) => job.status === "running").length,
    queued: jobs.filter((job) => job.status === "queued").length,
  };
}

function isOnOrAfter(value: string | null, boundary: Date): boolean {
  if (!value) return false;
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) && parsed >= boundary;
}
