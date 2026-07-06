import { useEffect, useState } from "react";
import { RefreshCw, Trash2 } from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { clearIndex, getAdminOverview } from "../../../services/api";
import type { AdminOverviewResponse } from "../../../services/types";
import {
  BlueprintLayout,
  BlueprintMetric,
  BlueprintMetricGrid,
  BlueprintPage,
  BlueprintPanel,
} from "../AdminBlueprintPrimitives";
import { StatusRow } from "../AdminPrimitives";

const CONFIRM_TEXT = "CLEAR INDEX";

export function AdminVectorIndexPage() {
  const { refreshOverview, setError: setGlobalError } = useAppData();
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isClearing, setClearing] = useState(false);
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
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
      setConfirmation("");
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
  const jobs = overview?.ingestion_jobs;
  const ready = !!index?.child_chunk_count && index.readiness_percent >= 100;

  return (
    <BlueprintPage>
      <BlueprintMetricGrid>
        <BlueprintMetric
          detail="indexed records"
          label="Documents"
          tone={index?.document_count ? "ok" : "warn"}
          value={formatMetric(index?.document_count)}
        />
        <BlueprintMetric
          detail="retrieval groups"
          label="Parent Chunks"
          value={formatMetric(index?.parent_chunk_count)}
        />
        <BlueprintMetric
          detail="searchable chunks"
          label="Child Chunks"
          value={formatMetric(index?.child_chunk_count)}
        />
        <BlueprintMetric
          detail={`${formatPercent(index?.readiness_percent)} ready`}
          label="Vectors"
          tone={ready ? "ok" : "warn"}
          value={formatMetric(index?.vector_count)}
        />
      </BlueprintMetricGrid>

      <BlueprintLayout>
        <BlueprintPanel
          description="Live counts from the backend document, chunk, and pgvector index tables"
          title="Index Readiness"
        >
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
          <div className="status-list">
            <StatusRow label="Readiness" value={formatPercent(index?.readiness_percent)} />
            <StatusRow label="Documents" value={formatMetric(index?.document_count)} />
            <StatusRow label="Parent chunks" value={formatMetric(index?.parent_chunk_count)} />
            <StatusRow label="Child chunks" value={formatMetric(index?.child_chunk_count)} />
            <StatusRow label="Vectors" value={formatMetric(index?.vector_count)} />
            <StatusRow label="Embedding model" value={overview?.health.embedding_model ?? "-"} />
            <StatusRow label="LLM model" value={overview?.health.llm_model ?? "-"} />
            <StatusRow label="LLM host" value={overview?.health.llm_host ?? "-"} />
          </div>
        )}
        </BlueprintPanel>

        <BlueprintPanel
          description="Latest job totals from the ingestion job store"
          title="Index Build State"
        >
        <div className="status-list">
          <StatusRow label="Jobs" value={formatMetric(jobs?.total)} />
          <StatusRow label="Queued" value={formatMetric(jobs?.queued)} />
          <StatusRow label="Running" value={formatMetric(jobs?.running)} />
          <StatusRow label="Completed" value={formatMetric(jobs?.completed)} />
          <StatusRow label="Failed" value={formatMetric(jobs?.failed)} />
          <StatusRow label="Last completed" value={formatDateTime(jobs?.last_completed_at)} />
        </div>
        </BlueprintPanel>

        <BlueprintPanel
          className="danger-panel"
          description="Maintenance action for rebuilding local retrieval data"
          title="Clear Index"
        >
        <p className="danger-copy">
          Clears indexed documents, parent chunks, child chunks, and embedding vectors from the backend index.
          Source files and exported artifacts are not deleted.
        </p>
        <Button
          disabled={isClearing}
          icon={<Trash2 size={17} />}
          onClick={() => setDialogOpen(true)}
          variant="danger"
        >
          {isClearing ? "Clearing" : "Clear Index"}
        </Button>
        </BlueprintPanel>
      </BlueprintLayout>

      <ConfirmDialog
        confirmDisabled={confirmation !== CONFIRM_TEXT || isClearing}
        confirmLabel={isClearing ? "Clearing" : "Clear Index"}
        isOpen={isDialogOpen}
        onCancel={() => {
          setDialogOpen(false);
          setConfirmation("");
        }}
        onConfirm={() => void confirmClear()}
        title="Clear indexed data?"
      >
        <p>
          Type <strong>{CONFIRM_TEXT}</strong> to confirm. This removes database index records and embeddings.
        </p>
        <label>
          <span>Confirmation</span>
          <input
            autoFocus
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={CONFIRM_TEXT}
            value={confirmation}
          />
        </label>
      </ConfirmDialog>
    </BlueprintPage>
  );
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}

function formatPercent(value: number | null | undefined): string {
  return typeof value === "number" ? `${Math.round(value * 10) / 10}%` : "-";
}
