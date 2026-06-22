import { Bot, Database, Gauge, HeartPulse, Sparkles } from "lucide-react";
import { useMemo } from "react";
import { useAppData } from "../../../app/AppDataContext";
import { MetricCard } from "../../../components/MetricCard";
import { Panel } from "../../../components/ui/Panel";
import { asText, summarizeDocuments } from "../../../lib/format";
import { useAdminWorkbench } from "../AdminWorkbenchContext";
import { PerfMetric } from "../AdminPrimitives";
import { buildImprovementAreas } from "../improvements";

export function AdminOverviewPage() {
  const { documents, health } = useAppData();
  const { searchResult, timings } = useAdminWorkbench();
  const stats = summarizeDocuments(documents?.documents ?? []);
  const improvementAreas = useMemo(
    () => buildImprovementAreas(health, documents, searchResult),
    [documents, health, searchResult],
  );

  return (
    <>
      <section className="metrics-grid" aria-label="System overview">
        <MetricCard
          icon={<HeartPulse size={20} />}
          label="API"
          value={health?.status ?? "loading"}
          tone={health?.status}
        />
        <MetricCard
          icon={<Database size={20} />}
          label="Documents"
          value={documents ? String(documents.total) : "loading"}
          detail={`${stats.parentChunks} parent / ${stats.childChunks} child`}
        />
        <MetricCard
          icon={<Sparkles size={20} />}
          label="Embedding"
          value={asText(health?.embedding.details.model) || "loading"}
          detail={`${asText(health?.embedding.details.dimensions) || "-"} dimensions`}
        />
        <MetricCard
          icon={<Bot size={20} />}
          label="LLM"
          value={asText(health?.llm.details.model) || "loading"}
          detail={asText(health?.llm.details.host)}
        />
      </section>

      <section className="admin-grid">
        <Panel
          className="wide-panel"
          eyebrow="Performance"
          icon={<Gauge size={20} />}
          title="Last Runs"
        >
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
    </>
  );
}
