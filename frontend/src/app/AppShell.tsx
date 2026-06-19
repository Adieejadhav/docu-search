import type { ReactNode } from "react";
import { Database, RefreshCw, Server, Sparkles } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAppData } from "./AppDataContext";
import { API_BASE_URL } from "../services/api";
import { primaryNavigation, titleForPath } from "./navigation";

export function AppShell({
  onRefresh,
  refreshDisabled,
  children,
}: {
  onRefresh: () => void;
  refreshDisabled: boolean;
  children: ReactNode;
}) {
  const location = useLocation();
  const { documents, health } = useAppData();
  const title = titleForPath(location.pathname);
  const isChatRoute = location.pathname.startsWith("/chat");

  if (isChatRoute) {
    return (
      <main className="min-h-screen bg-[#f7f7f5] text-slate-900">
        {children}
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Sparkles size={20} />
          </div>
          <div>
            <p>Docu Search</p>
            <strong>RAG Console</strong>
          </div>
        </div>

        <nav className="section-tabs" aria-label="Application sections">
          {primaryNavigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                className={({ isActive }) =>
                  isActive ||
                  (item.section === "admin" && location.pathname.startsWith("/admin"))
                    ? "active"
                    : ""
                }
                key={item.to}
                to={item.to}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <section className="sidebar-status">
          <div>
            <span className={`status-dot ${health?.status ?? "degraded"}`} />
            <span>{health?.status ?? "connecting"}</span>
          </div>
          <div>
            <Database size={15} />
            <span>{documents ? `${documents.total} documents` : "Loading index"}</span>
          </div>
          <div>
            <Server size={15} />
            <span>pgvector</span>
          </div>
        </section>
      </aside>

      <section className="app-main">
        <header className="topbar">
          <div>
            <p className="eyebrow">{location.pathname.startsWith("/admin") ? "Operations" : "Workspace"}</p>
            <h1>{title}</h1>
          </div>
          <div className="topbar-actions">
            <code>{API_BASE_URL}</code>
            <button
              className="icon-button"
              type="button"
              onClick={onRefresh}
              disabled={refreshDisabled}
              title="Refresh"
            >
              <RefreshCw size={18} />
            </button>
          </div>
        </header>
        <div className="page-content">{children}</div>
      </section>
    </main>
  );
}
