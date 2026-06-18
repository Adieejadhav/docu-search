import { useEffect, useState } from "react";
import { Activity, RefreshCw, Trash2 } from "lucide-react";
import { MarkdownAnswer } from "../../../components/MarkdownAnswer";
import { ResultItem } from "../../../components/ResultItem";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Panel } from "../../../components/ui/Panel";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { clearRagTraces, getRagTrace, listRagTraces } from "../../../services/api";
import type { RagTraceDetail, RagTraceSummary } from "../../../services/types";

export function AdminTracesPage() {
  const [traces, setTraces] = useState<RagTraceSummary[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<RagTraceDetail | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isLoadingDetail, setLoadingDetail] = useState(false);
  const [isClearOpen, setClearOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshTraces();
  }, []);

  async function refreshTraces() {
    setLoading(true);
    setError(null);
    try {
      const payload = await listRagTraces();
      setTraces(payload.traces);
      if (payload.traces.length) {
        await selectTrace(payload.traces[0].id);
      } else {
        setSelectedTrace(null);
      }
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoading(false);
    }
  }

  async function selectTrace(traceId: string) {
    setLoadingDetail(true);
    setError(null);
    try {
      setSelectedTrace(await getRagTrace(traceId));
    } catch (caught) {
      setError(messageFromError(caught));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function confirmClear() {
    setError(null);
    try {
      await clearRagTraces();
      setClearOpen(false);
      await refreshTraces();
    } catch (caught) {
      setError(messageFromError(caught));
    }
  }

  return (
    <section className="trace-layout">
      <Panel eyebrow="RAG Observability" icon={<Activity size={20} />} title="Trace History">
        <div className="panel-toolbar">
          <Button icon={<RefreshCw size={16} />} onClick={() => void refreshTraces()}>
            Refresh
          </Button>
          <Button
            disabled={!traces.length}
            icon={<Trash2 size={16} />}
            onClick={() => setClearOpen(true)}
            variant="danger"
          >
            Clear
          </Button>
        </div>
        {error && <div className="selection-error">{error}</div>}
        {isLoading ? (
          <Skeleton count={5} />
        ) : traces.length ? (
          <div className="trace-list">
            {traces.map((trace) => (
              <button
                className={
                  trace.id === selectedTrace?.id ? "trace-row active" : "trace-row"
                }
                key={trace.id}
                onClick={() => void selectTrace(trace.id)}
                type="button"
              >
                <strong>{trace.query}</strong>
                <span>
                  {formatDateTime(trace.created_at)} · {trace.total_ms.toFixed(0)}ms ·{" "}
                  {trace.result_count} sources
                </span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState>No RAG traces recorded yet.</EmptyState>
        )}
      </Panel>

      <Panel
        eyebrow="Trace Detail"
        title={selectedTrace ? selectedTrace.llm_model : "No trace selected"}
      >
        {isLoadingDetail && <Skeleton count={4} />}
        {!isLoadingDetail && selectedTrace && (
          <div className="trace-detail">
            <div className="trace-metrics">
              <span>retrieval {selectedTrace.retrieval_ms.toFixed(1)}ms</span>
              <span>answer {selectedTrace.answer_ms.toFixed(1)}ms</span>
              <span>{selectedTrace.embedding_model}</span>
            </div>
            <h3>{selectedTrace.query}</h3>
            <MarkdownAnswer text={selectedTrace.answer} />
            <div className="results-list">
              {selectedTrace.retrieval.results.map((result) => (
                <ResultItem key={result.child_chunk_id} result={result} />
              ))}
            </div>
          </div>
        )}
        {!isLoadingDetail && !selectedTrace && (
          <EmptyState icon={<Activity size={22} />}>Run chat or test bench to create traces.</EmptyState>
        )}
      </Panel>

      <ConfirmDialog
        confirmLabel="Clear Traces"
        isOpen={isClearOpen}
        onCancel={() => setClearOpen(false)}
        onConfirm={() => void confirmClear()}
        title="Clear RAG traces?"
      >
        <p>This removes stored trace history only. Documents, chunks, and embeddings remain.</p>
      </ConfirmDialog>
    </section>
  );
}
