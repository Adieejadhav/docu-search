import type { CSSProperties, ReactNode } from "react";
import { Sparkles } from "lucide-react";
import { NavLink } from "react-router-dom";

interface WorkspaceSidebarProps {
  after?: ReactNode;
  children: ReactNode;
  className?: string;
  footer?: ReactNode;
  isOpen?: boolean;
  onToggle?: () => void;
  style?: CSSProperties;
  subtitle: string;
}

interface WorkspaceSidebarItemProps {
  active?: boolean;
  icon?: ReactNode;
  label: string;
  onClick?: () => void;
  to?: string;
  trailing?: ReactNode;
}

export function WorkspaceSidebar({
  after,
  children,
  className = "",
  footer,
  isOpen = true,
  onToggle,
  style,
  subtitle,
}: WorkspaceSidebarProps) {
  return (
    <aside className={`workspace-sidebar ${className}`.trim()} style={style}>
      <div className="workspace-sidebar-inner">
        <header className="workspace-sidebar-brand">
          <button
            aria-expanded={isOpen}
            aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
            className="workspace-sidebar-logo"
            onClick={onToggle}
            title={isOpen ? "Collapse sidebar" : "Expand sidebar"}
            type="button"
          >
            <Sparkles size={18} />
          </button>
          <div className="workspace-sidebar-title">
            <strong>Docu Search</strong>
            <span>{subtitle}</span>
          </div>
        </header>

        <div className="workspace-sidebar-content">{children}</div>
        {footer && <footer className="workspace-sidebar-footer">{footer}</footer>}
      </div>
      {after}
    </aside>
  );
}

export function WorkspaceSidebarItem({
  active = false,
  icon,
  label,
  onClick,
  to,
  trailing,
}: WorkspaceSidebarItemProps) {
  const content = (
    <>
      {icon && <span className="workspace-sidebar-item-icon">{icon}</span>}
      <span className="workspace-sidebar-item-copy">
        <strong>{label}</strong>
      </span>
    </>
  );

  if (to) {
    return (
      <NavLink
        className={({ isActive }) =>
          `workspace-sidebar-item ${isActive ? "active" : ""}`.trim()
        }
        to={to}
      >
        {content}
      </NavLink>
    );
  }

  const item = (
    <button
      className={`workspace-sidebar-item ${active ? "active" : ""}`.trim()}
      onClick={onClick}
      type="button"
    >
      {content}
    </button>
  );

  if (!trailing) return item;

  return (
    <div className={`workspace-sidebar-entry ${active ? "active" : ""}`.trim()}>
      {item}
      <div className="workspace-sidebar-trailing">{trailing}</div>
    </div>
  );
}
