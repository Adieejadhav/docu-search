import { useEffect, useState } from "react";
import { Activity, ArrowLeft, RefreshCw } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { MarkdownAnswer } from "../../../components/MarkdownAnswer";
import { ResultItem } from "../../../components/ResultItem";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { getRagTrace } from "../../../services/api";
import type { RagTraceDetail } from "../../../services/types";
import { BlueprintPage, BlueprintPanel } from "../AdminBlueprintPrimitives";

export function AdminTraceDetailPage() {
  const { traceId } = useParams();
  const navigate = useNavigate();
  const [trace, setTrace] = useState<RagTraceDetail | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadTrace();
  }, [traceId]);

  async function loadTrace() {
    if (!traceId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      setTrace(await getRagTrace(traceId));
    } catch (caught) {
      setTrace(null);
      setError(messageFromError(caught));
    } finally {
      setLoading(false);
    }
  }

  return (
    <BlueprintPage>
      <section className="ops-panel ops-panel-full document-detail-hero">
        <header>
          <div className="document-detail-title">
            <h2>Trace Details</h2>
            <p>
              {trace
                ? `Recorded ${formatDateTime(trace.created_at)}`
                : "Stored RAG request details"}
            </p>
          </div>
          <div className="document-detail-actions">
            <Button
              icon={<ArrowLeft size={16} />}
              onClick={() => navigate("/admin/traces")}
            >
              Back
            </Button>
            <Button
              disabled={isLoading || !traceId}
              icon={<RefreshCw size={16} />}
              onClick={() => void loadTrace()}
            >
              {isLoading ? "Refreshing" : "Refresh"}
            </Button>
          </div>
        </header>
      </section>

      {error && <div className="selection-error">{error}</div>}
      {isLoading ? (
        <BlueprintPanel title="Loading Trace">
          <Skeleton count={6} />
        </BlueprintPanel>
      ) : trace ? (
        <>
          <section className="ops-panel ops-panel-full">
            <header>
              <div>
                <h2>Trace Summary</h2>
                <p>Models, result count, and request timing</p>
              </div>
            </header>
            <div className="ops-panel-body">
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th>Language Model</th>
                      <th>Embedding Model</th>
                      <th>Results</th>
                      <th>Retrieval</th>
                      <th>Answer</th>
                      <th>Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>{trace.llm_model}</td>
                      <td>{trace.embedding_model}</td>
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
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section className="ops-panel ops-panel-full">
            <header>
              <div>
                <h2>Query</h2>
                <p>The question submitted for this request</p>
              </div>
            </header>
            <div className="ops-panel-body">
              <p className="trace-query">{trace.query}</p>
            </div>
          </section>

          <section className="ops-panel ops-panel-full">
            <header>
              <div>
                <h2>Generated Answer</h2>
                <p>The model response stored with this trace</p>
              </div>
            </header>
            <div className="ops-panel-body">
              <MarkdownAnswer text={trace.answer} />
            </div>
          </section>

          <section className="ops-panel ops-panel-full">
            <header>
              <div>
                <h2>Retrieved Chunks</h2>
                <p>Source passages used to generate the answer</p>
              </div>
            </header>
            <div className="ops-panel-body">
              {trace.retrieval.results.length ? (
                <div className="results-list">
                  {trace.retrieval.results.map((result) => (
                    <ResultItem key={result.child_chunk_id} result={result} />
                  ))}
                </div>
              ) : (
                <EmptyState>No chunks were retrieved for this trace.</EmptyState>
              )}
            </div>
          </section>
        </>
      ) : (
        <BlueprintPanel title="Trace Not Found">
          <EmptyState icon={<Activity size={22} />}>
            The selected trace could not be loaded.
          </EmptyState>
        </BlueprintPanel>
      )}
    </BlueprintPage>
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
