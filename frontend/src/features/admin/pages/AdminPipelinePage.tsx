import { useEffect, useMemo, useState } from "react";
import { UploadCloud } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { listIngestionJobs } from "../../../services/api";
import type { IngestionJob, IngestionJobStatus } from "../../../services/types";
import { BlueprintPage } from "../AdminBlueprintPrimitives";

export function AdminPipelinePage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [totalJobs, setTotalJobs] = useState(0);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const totals = useMemo(
    () =>
      jobs.reduce(
        (summary, job) => ({
          parsedDocuments: summary.parsedDocuments + job.parsed_document_count,
          indexedChunks: summary.indexedChunks + job.indexed_child_count,
          failures: summary.failures + job.failure_count,
          completed: summary.completed + (job.status === "completed" ? 1 : 0),
        }),
        {
          parsedDocuments: 0,
          indexedChunks: 0,
          failures: 0,
          completed: 0,
        },
      ),
    [jobs],
  );

  useEffect(() => {
    void refreshJobs();
  }, []);

  async function refreshJobs() {
    setLoading(true);
    setError(null);
    try {
      const payload = await listIngestionJobs({ limit: 100 });
      setJobs(payload.jobs);
      setTotalJobs(payload.total);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <BlueprintPage>
      <section
        className="document-summary-strip"
        aria-label="Ingestion jobs summary"
      >
        <SummaryCard
          detail={`${formatMetric(totals.completed)} completed`}
          label="Total Jobs"
          value={formatMetric(totalJobs)}
        />
        <SummaryCard
          detail="documents extracted"
          label="Parsed Docs"
          value={formatMetric(totals.parsedDocuments)}
        />
        <SummaryCard
          detail={`${formatMetric(totals.failures)} failures`}
          label="Indexed Chunks"
          value={formatMetric(totals.indexedChunks)}
        />
      </section>

      <section className="ops-panel ops-panel-full">
        <header>
          <div>
            <h2>Ingestion Jobs</h2>
            <p>Jobs currently stored by the document ingestion pipeline</p>
          </div>
        </header>
        <div className="ops-panel-body">
          {error && <div className="selection-error">{error}</div>}
          {isLoading ? (
            <EmptyState icon={<UploadCloud size={22} />}>
              Loading ingestion jobs.
            </EmptyState>
          ) : (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Status</th>
                    <th>Files</th>
                    <th>Parsed docs</th>
                    <th>Indexed chunks</th>
                    <th>Failures</th>
                    <th>Updated</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.length ? (
                    jobs.map((job) => (
                      <JobRow
                        job={job}
                        key={job.id}
                        onView={() =>
                          navigate(`/admin/pipeline/${encodeURIComponent(job.id)}`)
                        }
                      />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8}>No ingestion jobs.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </BlueprintPage>
  );
}

function SummaryCard({
  detail,
  label,
  value,
}: {
  detail: string;
  label: string;
  value: string;
}) {
  return (
    <article className="document-summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function JobRow({
  job,
  onView,
}: {
  job: IngestionJob;
  onView: () => void;
}) {
  return (
    <tr>
      <td>
        <strong>{titleCase(job.source_kind)} import</strong>
        <br />
        <small>{shortId(job.id)}</small>
      </td>
      <td>
        <StatusPill status={job.status} />
      </td>
      <td>
        <span className="document-table-pill parent">
          {formatMetric(job.file_count)}
        </span>
      </td>
      <td>
        <span className="document-table-pill parent">
          {formatMetric(job.parsed_document_count)}
        </span>
      </td>
      <td>
        <span className="document-table-pill child">
          {formatMetric(job.indexed_child_count)}
        </span>
      </td>
      <td>
        <span
          className={
            job.failure_count
              ? "overview-table-pill danger"
              : "overview-table-pill muted"
          }
        >
          {formatMetric(job.failure_count)}
        </span>
      </td>
      <td>{formatDateTime(job.updated_at)}</td>
      <td>
        <button onClick={onView} type="button">
          View
        </button>
      </td>
    </tr>
  );
}

function StatusPill({ status }: { status: IngestionJobStatus }) {
  const className =
    status === "completed"
      ? "overview-table-pill ok"
      : status === "failed"
        ? "overview-table-pill danger"
        : status === "running"
          ? "overview-table-pill chunks"
          : "overview-table-pill warn";

  return <span className={className}>{titleCase(status)}</span>;
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(
      /\w\S*/g,
      (word) => `${word.charAt(0).toUpperCase()}${word.slice(1).toLowerCase()}`,
    );
}
