import type { ReactNode } from "react";

export function EmptyState({
  children,
  compact,
  icon,
}: {
  children: ReactNode;
  compact?: boolean;
  icon?: ReactNode;
}) {
  return (
    <div className={compact ? "empty-state compact" : "empty-state"}>
      {icon}
      <span>{children}</span>
    </div>
  );
}
