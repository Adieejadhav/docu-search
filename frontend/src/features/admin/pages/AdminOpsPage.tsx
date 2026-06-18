import { useEffect, useMemo, useState } from "react";
import { Activity, ShieldAlert, Trash2 } from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { Panel } from "../../../components/ui/Panel";
import { getApiMetrics } from "../../../services/api";
import type { ApiMetricsSnapshot } from "../../../services/types";
import { useAdminWorkbench } from "../AdminWorkbenchContext";
import { PerfMetric } from "../AdminPrimitives";
import { buildImprovementAreas } from "../improvements";

const CONFIRM_TEXT = "CLEAR INDEX";

export function AdminOpsPage() {
  const { documents, health } = useAppData();
  const { isLoading, runClearIndex, searchResult } = useAdminWorkbench();
  const [isDialogOpen, setDialogOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [metrics, setMetrics] = useState<ApiMetricsSnapshot | null>(null);
  const improvementAreas = useMemo(
    () => buildImprovementAreas(health, documents, searchResult),
    [documents, health, searchResult],
  );

  async function confirmClear() {
    await runClearIndex();
    setDialogOpen(false);
    setConfirmation("");
  }

  useEffect(() => {
    void refreshMetrics();
  }, []);

  async function refreshMetrics() {
    try {
      setMetrics(await getApiMetrics());
    } catch {
      setMetrics(null);
    }
  }

  return (
    <section className="admin-grid">
      <Panel className="danger-panel" eyebrow="Admin" icon={<ShieldAlert size={20} />} title="Index Clear">
        <p className="danger-copy">
          Clears indexed documents, parent chunks, child chunks, and embedding vectors from
          PostgreSQL/pgvector. Source files and exported JSON artifacts are not deleted.
        </p>
        <Button
          disabled={isLoading("clear")}
          icon={<Trash2 size={17} />}
          onClick={() => setDialogOpen(true)}
          variant="danger"
        >
          {isLoading("clear") ? "Clearing" : "Clear Index"}
        </Button>
      </Panel>

      <Panel eyebrow="Operational Notes" title="Next Controls">
        <ul className="improvement-list">
          {improvementAreas.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Panel>

      <Panel
        className="wide-panel"
        eyebrow="API Metrics"
        icon={<Activity size={20} />}
        title="Request Snapshot"
      >
        <div className="perf-grid">
          <PerfMetric label="Total" value={metrics?.total_count} />
          <PerfMetric label="Success" value={metrics?.success_count} />
          <PerfMetric label="Failure" value={metrics?.failure_count} />
        </div>
        <div className="operation-list">
          {Object.entries(metrics?.success_by_operation ?? {})
            .slice(0, 8)
            .map(([operation, count]) => (
              <div className="status-row" key={operation}>
                <span>{operation}</span>
                <strong>{count}</strong>
              </div>
            ))}
        </div>
      </Panel>

      <ConfirmDialog
        confirmDisabled={confirmation !== CONFIRM_TEXT || isLoading("clear")}
        confirmLabel={isLoading("clear") ? "Clearing" : "Clear Index"}
        isOpen={isDialogOpen}
        onCancel={() => {
          setDialogOpen(false);
          setConfirmation("");
        }}
        onConfirm={() => void confirmClear()}
        title="Clear indexed data?"
      >
        <p>
          Type <strong>{CONFIRM_TEXT}</strong> to confirm. This removes database index
          records and embeddings.
        </p>
        <label>
          <span>Confirmation</span>
          <input
            autoFocus
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            placeholder={CONFIRM_TEXT}
          />
        </label>
      </ConfirmDialog>
    </section>
  );
}
