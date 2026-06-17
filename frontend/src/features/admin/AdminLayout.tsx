import { Bot, Database, HeartPulse, Sparkles } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAppData } from "../../app/AppDataContext";
import { adminNavigation } from "../../app/navigation";
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
        <nav className="admin-tabs" aria-label="Admin sections">
          {adminNavigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink className={({ isActive }) => (isActive ? "active" : "")} key={item.to} to={item.to}>
                <Icon size={17} />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <Outlet />
      </section>
    </>
  );
}
