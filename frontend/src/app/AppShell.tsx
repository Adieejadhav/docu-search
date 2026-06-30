import type { ReactNode } from "react";
import { Database, Moon, RefreshCw, Sparkles, Sun } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAppData } from "./AppDataContext";
import { useTheme } from "./ThemeContext";
import { API_BASE_URL } from "../services/api";
import { adminNavigation, navigationItemForPath, primaryNavigation, titleForPath } from "./navigation";

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
  const activeItem = navigationItemForPath(location.pathname);
  const title = activeItem?.title ?? titleForPath(location.pathname);
  const eyebrow = activeItem?.eyebrow ?? (location.pathname.startsWith("/admin") ? "Operations" : "Workspace");
  const description = activeItem?.description;
  const isChatRoute = location.pathname.startsWith("/chat");
  const chatNavigation = primaryNavigation.find((item) => item.section === "chat");
  const ChatIcon = chatNavigation?.icon;
  const isAdminRoute = location.pathname.startsWith("/admin");

  if (isChatRoute) {
    return (
      <main className="chat-route-shell min-h-screen bg-slate-50 text-slate-900">
        <ThemeToggle compact />
        {children}
      </main>
    );
  }

  return (
    <main className="app-shell admin-blueprint-shell">
      <aside className="app-sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Sparkles size={20} />
          </div>
          <div>
            <strong>Docu Search</strong>
            <p>Admin workspace</p>
          </div>
        </div>

        <nav className="section-tabs" aria-label="Application sections">
          {chatNavigation && ChatIcon && (
            <NavLink
              className={({ isActive }) => (isActive ? "active" : "")}
              to={chatNavigation.to}
            >
              <ChatIcon size={18} />
              <span>{chatNavigation.label}</span>
            </NavLink>
          )}

          <p className="nav-group-label">Administration</p>
          {adminNavigation.map((item) => {
            const itemIndex = adminNavigation.findIndex((entry) => entry.to === item.to) + 1;
            return (
              <NavLink
                className={({ isActive }) => (isActive ? "active" : "")}
                key={item.to}
                to={item.to}
              >
                <span className="nav-index">{String(itemIndex).padStart(2, "0")}</span>
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
        </section>
      </aside>

      <section className="app-main">
        <header className="topbar">
          <div className="topbar-copy">
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            {description && <p className="topbar-description">{description}</p>}
          </div>
          <div className="topbar-right">
            {isAdminRoute && (
              <div className="admin-runtime-pills" aria-label="Runtime status">
                <span className="admin-pill"><i />Local</span>
                <span className={`admin-pill ${health?.status === "ok" ? "ok" : "warn"}`}><i />API {health?.status === "ok" ? "healthy" : "degraded"}</span>
                <span className={`admin-pill ${documents?.total ? "ok" : "warn"}`}><i />Vector {documents?.total ? "ready" : "pending"}</span>
                <span className={`admin-pill ${health?.llm.status === "ok" ? "ok" : "warn"}`}><i />LLM {health?.llm.status === "ok" ? "online" : "degraded"}</span>
              </div>
            )}
            <div className="topbar-actions">
              {!isAdminRoute && <code>{API_BASE_URL}</code>}
              {isAdminRoute && (
                <>
                  <NavLink className="admin-action" to="/admin/playground">Playground</NavLink>
                  <NavLink className="admin-action primary" to="/admin/evaluations">Run Eval</NavLink>
                </>
              )}
              <ThemeToggle />
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
          </div>
        </header>
        <div className="page-content">{children}</div>
      </section>
    </main>
  );
}

function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Sun : Moon;

  return (
    <button
      aria-label={`Switch to ${nextTheme} mode`}
      className={compact ? "theme-toggle chat-theme-toggle" : "theme-toggle"}
      onClick={toggleTheme}
      title={`Switch to ${nextTheme} mode`}
      type="button"
    >
      <Icon size={17} />
      {!compact && <span>{theme === "dark" ? "Light" : "Dark"}</span>}
    </button>
  );
}
