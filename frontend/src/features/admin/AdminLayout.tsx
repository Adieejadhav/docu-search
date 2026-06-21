import { Bot, Database, HeartPulse, Sparkles } from "lucide-react";
import { Outlet } from "react-router-dom";
import { useAppData } from "../../app/AppDataContext";
import { MetricCard } from "../../components/MetricCard";
import { asText, summarizeDocuments } from "../../lib/format";

export function AdminLayout() {
  const { documents, health } = useAppData();
  const stats = summarizeDocuments(documents?.documents ?? []);

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

      <section className="admin-shell">
        <Outlet />
      </section>
    </>
  );
}
