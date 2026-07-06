import { useEffect, useMemo, useState } from "react";
import { Activity, RefreshCw, UploadCloud } from "lucide-react";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { getIngestionJob, listIngestionJobs } from "../../../services/api";
import type {
  IngestionJob,
  IngestionJobEvent,
  IngestionJobStatus,
} from "../../../services/types";
import {
  BlueprintBadge,
  BlueprintLayout,
  BlueprintMetric,
  BlueprintMetricGrid,
  BlueprintPage,
  BlueprintPanel,
  type BlueprintTone,
} from "../AdminBlueprintPrimitives";

export function AdminPipelinePage() {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<IngestionJob | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isLoadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totals = useMemo(
    () =>
      jobs.reduce(
        (summary, job) => ({
          files: summary.files + job.file_count,
          parsed: summary.parsed + job.parsed_document_count,
          indexed: summary.indexed + job.indexed_child_count,
          failures: summary.failures + job.failure_count,
        }),
        { files: 0, parsed: 0, indexed: 0, failures: 0 },
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
      const payload = await listIngestionJobs({ limit: 25 });
      setJobs(payload.jobs);
      if (payload.jobs.length) {
        await selectJob(payload.jobs[0].id);
      } else {
        setSelectedJob(null);
      }
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoading(false);
    }
  }

  async function selectJob(jobId: string) {
    setLoadingDetail(true);
    setError(null);
    try {
      setSelectedJob(await getIngestionJob(jobId));
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoadingDetail(false);
    }
  }

  return (
    <BlueprintPage>
      <BlueprintMetricGrid columns={5}>
        <BlueprintMetric label="Jobs" value={formatNumber(jobs.length)} detail="recent imports" />
        <BlueprintMetric label="Files" value={formatNumber(totals.files)} detail="uploaded inputs" tone="ok" />
        <BlueprintMetric label="Parsed docs" value={formatNumber(totals.parsed)} detail="documents extracted" />
        <BlueprintMetric label="Indexed chunks" value={formatNumber(totals.indexed)} detail="vectors queued" tone="ok" />
        <BlueprintMetric label="Failures" value={formatNumber(totals.failures)} detail="job-level failures" tone={totals.failures ? "danger" : "ok"} />
      </BlueprintMetricGrid>

      <BlueprintLayout>
        <BlueprintPanel
          description={jobs[0] ? `Latest update ${formatDateTime(jobs[0].updated_at)}` : "No ingestion activity yet"}
          title="Ingestion Jobs"
        >
        <div className="panel-toolbar">
          <Button
            disabled={isLoading}
            icon={<RefreshCw size={16} />}
            onClick={() => void refreshJobs()}
          >
            {isLoading ? "Refreshing" : "Refresh"}
          </Button>
        </div>
        {error && <div className="selection-error">{error}</div>}
        {isLoading ? (
          <Skeleton count={5} />
        ) : jobs.length ? (
          <div className="job-list">
            {jobs.map((job) => (
              <button
                className={job.id === selectedJob?.id ? "job-row active" : "job-row"}
                key={job.id}
                onClick={() => void selectJob(job.id)}
                type="button"
              >
                <span>
                  <strong>{titleCase(job.source_kind)} import</strong>
                  <small>
                    {shortId(job.id)} | {formatDateTime(job.updated_at)} | {job.file_count} file(s)
                  </small>
                </span>
                <StatusPill status={job.status} />
              </button>
            ))}
          </div>
        ) : (
          <EmptyState icon={<UploadCloud size={22} />}>No ingestion jobs have run yet.</EmptyState>
        )}
        </BlueprintPanel>

        <BlueprintPanel
          description="Stage timings, indexed counts, and the latest job events"
          title={selectedJob ? `Job ${shortId(selectedJob.id)}` : "No Job Selected"}
        >
        {isLoadingDetail && <Skeleton count={5} />}
        {!isLoadingDetail && selectedJob && <JobDetail job={selectedJob} />}
        {!isLoadingDetail && !selectedJob && (
          <EmptyState icon={<Activity size={22} />}>Select a job to inspect stage timings and events.</EmptyState>
        )}
        </BlueprintPanel>
      </BlueprintLayout>
    </BlueprintPage>
  );
}

function JobDetail({ job }: { job: IngestionJob }) {
  const timings = Object.entries(job.timings_ms ?? {});
  const recentEvents = job.events.slice(-20).reverse();

  return (
    <div className="job-detail">
      <div className="job-summary-grid">
        <JobStat label="Status" value={titleCase(job.status)} />
        <JobStat label="Files" value={formatNumber(job.file_count)} />
        <JobStat label="Parsed" value={formatNumber(job.parsed_document_count)} />
        <JobStat label="Parents" value={formatNumber(job.parent_chunk_count)} />
        <JobStat label="Children" value={formatNumber(job.child_chunk_count)} />
        <JobStat label="Indexed" value={formatNumber(job.indexed_child_count)} />
      </div>

      {job.error_message && (
        <div className="job-error">
          <strong>{job.error_code ?? "Job failed"}</strong>
          <span>{job.error_message}</span>
        </div>
      )}

      <div className="job-timings">
        <span>
          created <strong>{formatDateTime(job.created_at)}</strong>
        </span>
        <span>
          updated <strong>{formatDateTime(job.updated_at)}</strong>
        </span>
        <span>
          duration <strong>{formatDuration(totalDurationMs(job))}</strong>
        </span>
        {timings.map(([stage, duration]) => (
          <span key={stage}>
            {titleCase(stage)} <strong>{formatDuration(duration)}</strong>
          </span>
        ))}
      </div>

      {recentEvents.length ? (
        <div className="event-timeline">
          {recentEvents.map((event, index) => (
            <JobEventRow event={event} key={`${event.stage}-${event.timestamp ?? index}-${index}`} />
          ))}
        </div>
      ) : (
        <EmptyState compact>No job events recorded.</EmptyState>
      )}
    </div>
  );
}

function JobEventRow({ event }: { event: IngestionJobEvent }) {
  return (
    <article className="event-row">
      <span className={`event-dot ${event.status}`} />
      <div>
        <strong>{titleCase(event.stage)}</strong>
        <p>{event.message}</p>
        <small>
          {[event.path, formatDateTime(event.timestamp), formatDuration(event.duration_ms)]
            .filter((value) => value && value !== "-")
            .join(" | ")}
        </small>
      </div>
    </article>
  );
}

function JobStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="job-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusPill({ status }: { status: IngestionJobStatus }) {
  return <BlueprintBadge tone={statusTone(status)}>{titleCase(status)}</BlueprintBadge>;
}

function statusTone(status: IngestionJobStatus): BlueprintTone {
  if (status === "completed") return "ok";
  if (status === "failed") return "danger";
  if (status === "running") return "info";
  return "warn";
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

function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function shortId(value: string): string {
  return value.slice(0, 8);
}

function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\w\S*/g, (word) => `${word.charAt(0).toUpperCase()}${word.slice(1).toLowerCase()}`);
}
