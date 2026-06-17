import { Gauge } from "lucide-react";
import { useMemo } from "react";
import { useAppData } from "../../../app/AppDataContext";
import { Panel } from "../../../components/ui/Panel";
import { asText } from "../../../lib/format";
import { useAdminWorkbench } from "../AdminWorkbenchContext";
import { PerfMetric, StatusRow } from "../AdminPrimitives";
import { buildImprovementAreas } from "../improvements";

export function AdminOverviewPage() {
  const { documents, health } = useAppData();
  const { searchResult, timings } = useAdminWorkbench();
  const improvementAreas = useMemo(
    () => buildImprovementAreas(health, documents, searchResult),
    [documents, health, searchResult],
  );

  return (
    <section className="admin-grid">
      <Panel eyebrow="System Status" title="Backend Readiness">
        <div className="status-list">
          <StatusRow label="Database" value={health?.database.status ?? "loading"} />
          <StatusRow label="Embedding" value={asText(health?.embedding.details.model)} />
          <StatusRow label="LLM" value={asText(health?.llm.details.model)} />
          <StatusRow label="Indexed Documents" value={String(documents?.total ?? "-")} />
        </div>
      </Panel>

      <Panel eyebrow="Performance" icon={<Gauge size={20} />} title="Last Runs">
        <div className="perf-grid">
          <PerfMetric label="Search" value={timings.search} />
          <PerfMetric label="Ask" value={timings.ask} />
          <PerfMetric label="Clear" value={timings.clear} />
        </div>
      </Panel>

      <Panel className="wide-panel" eyebrow="Improvement Queue" title="Production Hardening">
        <ul className="improvement-list columns">
          {improvementAreas.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Panel>
    </section>
  );
}
