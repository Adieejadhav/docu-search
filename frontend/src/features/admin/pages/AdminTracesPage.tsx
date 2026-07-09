import { useEffect, useState } from "react";
import { Activity, RefreshCw, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { clearRagTraces, listRagTraces } from "../../../services/api";
import type { RagTraceSummary } from "../../../services/types";
import { BlueprintPage } from "../AdminBlueprintPrimitives";

export function AdminTracesPage() {
  const navigate = useNavigate();
  const [traces, setTraces] = useState<RagTraceSummary[]>([]);
  const [totalTraces, setTotalTraces] = useState(0);
  const [isLoading, setLoading] = useState(true);
  const [isClearing, setClearing] = useState(false);
  const [isClearOpen, setClearOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshTraces();
  }, []);

  async function refreshTraces() {
    setLoading(true);
    setError(null);
    try {
      const payload = await listRagTraces({ limit: 100 });
      setTraces(payload.traces);
      setTotalTraces(payload.total);
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoading(false);
    }
  }

  async function confirmClear() {
    setClearing(true);
    setError(null);
    try {
      await clearRagTraces();
      setClearOpen(false);
      await refreshTraces();
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setClearing(false);
    }
  }

  const retrievedChunkCount = traces.reduce(
    (total, trace) => total + trace.result_count,
    0,
  );
  const averageLatency = traces.length
    ? traces.reduce((total, trace) => total + trace.total_ms, 0) / traces.length
    : null;

  return (
    <BlueprintPage>
      <section className="document-summary-strip" aria-label="RAG trace summary">
        <SummaryCard
          detail="stored requests"
          label="Total Traces"
          value={formatMetric(totalTraces)}
        />
        <SummaryCard
          detail="latest loaded traces"
          label="Retrieved Chunks"
          value={formatMetric(retrievedChunkCount)}
        />
        <SummaryCard
          detail="latest loaded traces"
          label="Average Latency"
          value={formatDuration(averageLatency)}
        />
      </section>

      <section className="ops-panel ops-panel-full">
        <header>
          <div>
            <h2>Trace History</h2>
            <p>Stored RAG requests from chat and test bench</p>
          </div>
        </header>
        <div className="ops-panel-body">
          <div className="panel-toolbar">
            <Button
              disabled={isLoading}
              icon={<RefreshCw size={16} />}
              onClick={() => void refreshTraces()}
            >
              {isLoading ? "Refreshing" : "Refresh"}
            </Button>
            <Button
              disabled={!traces.length || isClearing}
              icon={<Trash2 size={16} />}
              onClick={() => setClearOpen(true)}
              variant="danger"
            >
              Clear Traces
            </Button>
          </div>

          {error && <div className="selection-error">{error}</div>}
          {isLoading ? (
            <EmptyState icon={<Activity size={22} />}>
              Loading trace history.
            </EmptyState>
          ) : (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Query</th>
                    <th>Results</th>
                    <th>Retrieval</th>
                    <th>Answer</th>
                    <th>Total</th>
                    <th>Model</th>
                    <th>Created</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {traces.length ? (
                    traces.map((trace) => (
                      <TraceRow
                        key={trace.id}
                        onView={() =>
                          navigate(`/admin/traces/${encodeURIComponent(trace.id)}`)
                        }
                        trace={trace}
                      />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8}>No RAG traces recorded yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      <ConfirmDialog
        confirmDisabled={isClearing}
        confirmLabel={isClearing ? "Clearing" : "Clear Traces"}
        isOpen={isClearOpen}
        onCancel={() => setClearOpen(false)}
        onConfirm={() => void confirmClear()}
        title="Clear RAG traces?"
      >
        <p>This removes stored trace history only. Documents, chunks, and embeddings remain.</p>
      </ConfirmDialog>
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

function TraceRow({
  onView,
  trace,
}: {
  onView: () => void;
  trace: RagTraceSummary;
}) {
  return (
    <tr className="trace-table-row">
      <td>
        <strong>{trace.query}</strong>
      </td>
      <td>
        <span className="overview-table-pill source">
          {formatMetric(trace.result_count)}
        </span>
      </td>
      <td>{formatDuration(trace.retrieval_ms)}</td>
      <td>{formatDuration(trace.answer_ms)}</td>
      <td>
        <span className="overview-table-pill latency">
          {formatDuration(trace.total_ms)}
        </span>
      </td>
      <td>{trace.llm_model}</td>
      <td>{formatDateTime(trace.created_at)}</td>
      <td>
        <button onClick={onView} type="button">
          View
        </button>
      </td>
    </tr>
  );
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}

function formatDuration(value: number | null | undefined): string {
  if (typeof value !== "number") return "-";
  if (value >= 1000) {
    const seconds = value / 1000;
    return `${seconds >= 10 ? Math.round(seconds) : seconds.toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}
