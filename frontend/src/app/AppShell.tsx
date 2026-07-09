import { useState, type ReactNode } from "react";
import { Database, Moon, Sun } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useAppData } from "./AppDataContext";
import { useTheme } from "./ThemeContext";
import { adminNavigation, navigationItemForPath, primaryNavigation, titleForPath } from "./navigation";
import { WorkspaceSidebar, WorkspaceSidebarItem } from "./WorkspaceSidebar";

export function AppShell({
  children,
}: {
  children: ReactNode;
}) {
  const location = useLocation();
  const [isAdminSidebarOpen, setAdminSidebarOpen] = useState(true);
  const { documents, health } = useAppData();
  const activeItem = navigationItemForPath(location.pathname);
  const title = activeItem?.title ?? titleForPath(location.pathname);
  const eyebrow = activeItem?.eyebrow ?? (location.pathname.startsWith("/admin") ? "Operations" : "Workspace");
  const description = activeItem?.description;
  const isChatRoute = location.pathname.startsWith("/chat");
  const chatNavigation = primaryNavigation.find((item) => item.section === "chat");
  const ChatIcon = chatNavigation?.icon;

  if (isChatRoute) {
    return (
      <main className="chat-route-shell min-h-screen bg-slate-50 text-slate-900">
        {children}
      </main>
    );
  }

  return (
    <main
      className={[
        "app-shell",
        "admin-blueprint-shell",
        isAdminSidebarOpen ? "" : "sidebar-collapsed",
      ].filter(Boolean).join(" ")}
    >
      <WorkspaceSidebar
        className={`app-sidebar ${isAdminSidebarOpen ? "open" : "closed"}`}
        footer={
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
        }
        isOpen={isAdminSidebarOpen}
        onToggle={() => setAdminSidebarOpen((current) => !current)}
        subtitle="Admin workspace"
      >
        <nav className="workspace-sidebar-nav" aria-label="Application sections">
          {chatNavigation && ChatIcon && (
            <WorkspaceSidebarItem
              icon={<ChatIcon size={17} />}
              label={chatNavigation.label}
              to={chatNavigation.to}
            />
          )}

          <p className="workspace-sidebar-label">Administration</p>
          {adminNavigation.map((item) => {
            const Icon = item.icon;
            return (
              <WorkspaceSidebarItem
                icon={<Icon size={17} />}
                key={item.to}
                label={item.label}
                to={item.to}
              />
            );
          })}
        </nav>
      </WorkspaceSidebar>

      <section className="app-main">
        <header className="topbar">
          <div className="topbar-copy">
            <p className="eyebrow">{eyebrow}</p>
            <h1>{title}</h1>
            {description && <p className="topbar-description">{description}</p>}
          </div>
          <div className="topbar-right">
            <div className="topbar-actions">
              <ThemeToggle />
            </div>
          </div>
        </header>
        <div className="page-content">{children}</div>
      </section>
    </main>
  );
}

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Sun : Moon;

  return (
    <button
      aria-label={`Switch to ${nextTheme} mode`}
      className="theme-toggle"
      onClick={toggleTheme}
      title={`Switch to ${nextTheme} mode`}
      type="button"
    >
      <Icon size={17} />
      <span>{theme === "dark" ? "Light" : "Dark"}</span>
    </button>
  );
}
