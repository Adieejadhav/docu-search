import { useEffect, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { Skeleton } from "../../../components/ui/Skeleton";
import { messageFromError } from "../../../lib/format";
import { clearIndex, getAdminOverview } from "../../../services/api";
import type { AdminOverviewResponse } from "../../../services/types";
import { BlueprintPage, BlueprintPanel } from "../AdminBlueprintPrimitives";

export function AdminVectorIndexPage() {
  const { refreshOverview, setError: setGlobalError } = useAppData();
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isClearing, setClearing] = useState(false);
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshIndex();
  }, []);

  async function refreshIndex() {
    setLoading(true);
    setError(null);
    setGlobalError(null);
    try {
      setOverview(await getAdminOverview());
    } catch (caught) {
      const message = messageFromError(caught);
      setError(message);
      setGlobalError(message);
    } finally {
      setLoading(false);
    }
  }

  async function confirmClear() {
    setClearing(true);
    setError(null);
    setGlobalError(null);
    try {
      await clearIndex();
      setDialogOpen(false);
      await Promise.all([refreshIndex(), refreshOverview("refresh")]);
    } catch (caught) {
      const message = messageFromError(caught);
      setError(message);
      setGlobalError(message);
    } finally {
      setClearing(false);
    }
  }

  const index = overview?.index;
  const childChunkCount = index?.child_chunk_count ?? 0;
  const vectorCount = index?.vector_count ?? 0;
  const missingVectorCount = Math.max(0, childChunkCount - vectorCount);
  const readinessPercent = index?.readiness_percent;

  return (
    <BlueprintPage>
      <section
        className="document-summary-strip index-summary-strip"
        aria-label="Search index summary"
      >
        <SummaryCard
          detail={indexStatus(readinessPercent, childChunkCount)}
          label="Readiness"
          value={formatPercent(readinessPercent)}
        />
        <SummaryCard
          detail="search records"
          label="Child Chunks"
          value={formatMetric(childChunkCount)}
        />
        <SummaryCard
          detail="embedded records"
          label="Embedding Vectors"
          value={formatMetric(vectorCount)}
        />
        <SummaryCard
          detail="coverage gaps"
          label="Missing Vectors"
          value={formatMetric(missingVectorCount)}
        />
        <SummaryCard
          detail="answer context"
          label="Parent Chunks"
          value={formatMetric(index?.parent_chunk_count)}
        />
      </section>

      <section className="ops-panel ops-panel-full">
        <header>
          <div>
            <h2>Search Index Health</h2>
            <p>Vector coverage and retrieval readiness for the active RAG index</p>
          </div>
        </header>
        <div className="ops-panel-body">
        <div className="panel-toolbar">
          <Button
            disabled={isLoading}
            icon={<RefreshCw size={16} />}
            onClick={() => void refreshIndex()}
          >
            {isLoading ? "Refreshing" : "Refresh"}
          </Button>
        </div>
        {error && <div className="selection-error">{error}</div>}
        {isLoading && !overview ? (
          <Skeleton count={4} />
        ) : (
          <div className="ops-table-wrap">
            <table className="ops-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Readiness</th>
                  <th>Vector Coverage</th>
                  <th>Missing Vectors</th>
                  <th>Embedding Model</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <span
                      className={`overview-table-pill ${indexTone(
                        readinessPercent,
                        childChunkCount,
                      )}`}
                    >
                      {indexStatus(readinessPercent, childChunkCount)}
                    </span>
                  </td>
                  <td>
                    <CoverageBar value={readinessPercent} />
                  </td>
                  <td>
                    {formatMetric(vectorCount)} / {formatMetric(childChunkCount)}
                  </td>
                  <td>
                    <span
                      className={
                        missingVectorCount
                          ? "overview-table-pill warn"
                          : "overview-table-pill ok"
                      }
                    >
                      {formatMetric(missingVectorCount)}
                    </span>
                  </td>
                  <td>{overview?.health.embedding_model ?? "-"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
        </div>
      </section>

      <BlueprintPanel className="danger-panel" title="Clear Search Index">
        <Button
          disabled={isClearing}
          icon={<Trash2 size={17} />}
          onClick={() => setDialogOpen(true)}
          variant="danger"
        >
          {isClearing ? "Clearing" : "Clear Index"}
        </Button>
      </BlueprintPanel>

      <ConfirmDialog
        confirmDisabled={isClearing}
        confirmLabel={isClearing ? "Clearing" : "Clear Index"}
        isOpen={isDialogOpen}
        onCancel={() => setDialogOpen(false)}
        onConfirm={() => void confirmClear()}
        title="Clear indexed data?"
      >
        <p>
          This removes indexed documents, chunks, and embedding vectors from the search index.
        </p>
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

function CoverageBar({ value }: { value: number | null | undefined }) {
  const boundedValue =
    typeof value === "number" ? Math.min(100, Math.max(0, value)) : 0;

  return (
    <span className="index-coverage-cell">
      <span className="blueprint-progress" aria-hidden="true">
        <i style={{ width: `${boundedValue}%` }} />
      </span>
      <strong>{formatPercent(value)}</strong>
    </span>
  );
}

function indexStatus(
  readinessPercent: number | null | undefined,
  childChunkCount: number,
): string {
  if (!childChunkCount) return "Empty";
  if (typeof readinessPercent !== "number") return "Loading";
  return readinessPercent >= 100 ? "Ready" : "Syncing";
}

function indexTone(
  readinessPercent: number | null | undefined,
  childChunkCount: number,
): "ok" | "warn" {
  if (!childChunkCount) return "warn";
  return typeof readinessPercent === "number" && readinessPercent >= 100
    ? "ok"
    : "warn";
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}

function formatPercent(value: number | null | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 10) / 10}%` : "-";
}
