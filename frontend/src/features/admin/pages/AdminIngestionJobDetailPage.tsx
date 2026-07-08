import { useEffect, useState } from "react";
import { ArrowLeft, UploadCloud } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { getIngestionJob } from "../../../services/api";
import type {
  IngestionJob,
  IngestionJobEvent,
  IngestionJobStatus,
} from "../../../services/types";
import { BlueprintPage, BlueprintPanel } from "../AdminBlueprintPrimitives";

export function AdminIngestionJobDetailPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadJob();
  }, [jobId]);

  async function loadJob() {
    if (!jobId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      setJob(await getIngestionJob(jobId));
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoading(false);
    }
  }

  const title = job ? `${titleCase(job.source_kind)} import` : "Ingestion Job";

  return (
    <BlueprintPage>
      <section className="ops-panel ops-panel-full document-detail-hero">
        <header>
          <div className="document-detail-title">
            <h2>{title}</h2>
            <p>{job ? `Job ${shortId(job.id)}` : "Ingestion job details and events"}</p>
          </div>
          <div className="document-detail-actions">
            <Button icon={<ArrowLeft size={16} />} onClick={() => navigate("/admin/pipeline")}>
              Back
            </Button>
          </div>
        </header>
      </section>

      {error && <div className="selection-error">{error}</div>}
      {isLoading ? (
        <BlueprintPanel title="Loading Ingestion Job">
          <Skeleton count={6} />
        </BlueprintPanel>
      ) : job ? (
        <>
          <JobSummary job={job} />
          <JobRuntime job={job} />
          <JobSources job={job} />
          <JobOptions job={job} />
          <JobEvents events={job.events} />
        </>
      ) : (
        <BlueprintPanel title="Job Not Found">
          <EmptyState icon={<UploadCloud size={22} />}>
            The selected ingestion job could not be loaded.
          </EmptyState>
        </BlueprintPanel>
      )}
    </BlueprintPage>
  );
}

function JobSummary({ job }: { job: IngestionJob }) {
  return (
    <section className="ops-panel ops-panel-full">
      <header>
        <div>
          <h2>Job Summary</h2>
          <p>Counts recorded by the ingestion pipeline</p>
        </div>
      </header>
      <div className="ops-panel-body">
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Source</th>
                <th>Files</th>
                <th>Discovered</th>
                <th>Parsed docs</th>
                <th>Parent chunks</th>
                <th>Child chunks</th>
                <th>Indexed chunks</th>
                <th>Failures</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <StatusPill status={job.status} />
                </td>
                <td>
                  <span className="document-table-pill type">
                    {job.source_kind}
                  </span>
                </td>
                <td>{formatMetric(job.file_count)}</td>
                <td>{formatMetric(job.discovered_input_files)}</td>
                <td>{formatMetric(job.parsed_document_count)}</td>
                <td>{formatMetric(job.parent_chunk_count)}</td>
                <td>{formatMetric(job.child_chunk_count)}</td>
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
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function JobRuntime({ job }: { job: IngestionJob }) {
  const timings = Object.entries(job.timings_ms ?? {});

  return (
    <section className="ops-panel ops-panel-full">
      <header>
        <div>
          <h2>Runtime</h2>
          <p>Lifecycle timestamps and stage timings</p>
        </div>
      </header>
      <div className="ops-panel-body">
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Created</th>
                <th>Started</th>
                <th>Completed</th>
                <th>Updated</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{formatDateTime(job.created_at)}</td>
                <td>{formatDateTime(job.started_at)}</td>
                <td>{formatDateTime(job.completed_at)}</td>
                <td>{formatDateTime(job.updated_at)}</td>
                <td>{formatDuration(totalDurationMs(job))}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {timings.length ? (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Duration</th>
                </tr>
              </thead>
              <tbody>
                {timings.map(([stage, duration]) => (
                  <tr key={stage}>
                    <td>{titleCase(stage)}</td>
                    <td>{formatDuration(duration)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState compact>No stage timings recorded.</EmptyState>
        )}
      </div>
    </section>
  );
}

function JobSources({ job }: { job: IngestionJob }) {
  return (
    <BlueprintPanel
      description="Input files attached to this ingestion job"
      title="Source Files"
    >
      {job.source_paths.length ? (
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Path</th>
              </tr>
            </thead>
            <tbody>
              {job.source_paths.map((path) => (
                <tr key={path}>
                  <td>{path}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState icon={<UploadCloud size={22} />}>
          No source files were recorded for this job.
        </EmptyState>
      )}
    </BlueprintPanel>
  );
}

function JobOptions({ job }: { job: IngestionJob }) {
  const options = Object.entries(job.options ?? {});

  return (
    <BlueprintPanel
      description="Execution options saved with this job"
      title="Job Options"
    >
      {options.length ? (
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Option</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {options.map(([key, value]) => (
                <tr key={key}>
                  <td>{titleCase(key)}</td>
                  <td>{formatValue(value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState compact>No job options recorded.</EmptyState>
      )}

      {job.error_message && (
        <div className="job-error">
          <strong>{job.error_code ?? "Job failed"}</strong>
          <span>{job.error_message}</span>
          {Object.keys(job.error_details ?? {}).length ? (
            <pre>{JSON.stringify(job.error_details, null, 2)}</pre>
          ) : null}
        </div>
      )}
    </BlueprintPanel>
  );
}

function JobEvents({ events }: { events: IngestionJobEvent[] }) {
  return (
    <BlueprintPanel
      description="Recorded progress events from discovery through indexing"
      title="Job Events"
    >
      {events.length ? (
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>
                <th>Stage</th>
                <th>Status</th>
                <th>Message</th>
                <th>Path</th>
                <th>Duration</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event, index) => (
                <EventRow
                  event={event}
                  key={`${event.stage}-${event.timestamp ?? index}-${index}`}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState compact>No job events recorded.</EmptyState>
      )}
    </BlueprintPanel>
  );
}

function EventRow({ event }: { event: IngestionJobEvent }) {
  return (
    <tr>
      <td>{titleCase(event.stage)}</td>
      <td>
        <span
          className={
            event.status === "completed"
              ? "overview-table-pill ok"
              : event.status === "failed"
                ? "overview-table-pill danger"
                : "overview-table-pill warn"
          }
        >
          {titleCase(event.status)}
        </span>
      </td>
      <td>{event.message}</td>
      <td>{event.path ?? "-"}</td>
      <td>{formatDuration(event.duration_ms)}</td>
      <td>{formatDateTime(event.timestamp)}</td>
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

function totalDurationMs(job: IngestionJob): number | null {
  if (!job.completed_at || !job.started_at) return null;

  const completedAt = new Date(job.completed_at).getTime();
  const startedAt = new Date(job.started_at).getTime();
  if (Number.isNaN(completedAt) || Number.isNaN(startedAt)) return null;

  return Math.max(0, completedAt - startedAt);
}

function formatDuration(value: number | null | undefined): string {
  if (typeof value !== "number") return "-";
  if (value >= 1000) {
    const seconds = value / 1000;
    return `${seconds >= 10 ? Math.round(seconds) : seconds.toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "-";
  return JSON.stringify(value);
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
