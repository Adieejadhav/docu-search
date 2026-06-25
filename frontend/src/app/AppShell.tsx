import type { ReactNode } from "react";
import { Database, Moon, RefreshCw, Sparkles, Sun } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAppData } from "./AppDataContext";
import { useTheme } from "./ThemeContext";
import { API_BASE_URL } from "../services/api";
import { adminNavigation, primaryNavigation, titleForPath } from "./navigation";

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
  const chatNavigation = primaryNavigation.find((item) => item.section === "chat");
  const ChatIcon = chatNavigation?.icon;

  if (isChatRoute) {
    return (
      <main className="chat-route-shell min-h-screen bg-slate-50 text-slate-900">
        <ThemeToggle compact />
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
            const Icon = item.icon;
            return (
              <NavLink
                className={({ isActive }) => (isActive ? "active" : "")}
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
