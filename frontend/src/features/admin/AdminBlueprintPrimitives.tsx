import type { ReactNode } from "react";

export type BlueprintTone = "ok" | "warn" | "info" | "mute" | "danger";

export function BlueprintPage({ children }: { children: ReactNode }) {
  return <div className="blueprint-page">{children}</div>;
}

export function BlueprintPanel({
  children,
  className,
  description,
  title,
}: {
  children: ReactNode;
  className?: string;
  description?: string;
  title: string;
}) {
  return (
    <section className={["blueprint-panel", className].filter(Boolean).join(" ")}>
      <header>
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
      </header>
      <div className="blueprint-panel-body">{children}</div>
    </section>
  );
}

export function BlueprintMetricGrid({
  children,
  columns = 4,
}: {
  children: ReactNode;
  columns?: 4 | 5;
}) {
  return <section className={`blueprint-metric-grid columns-${columns}`}>{children}</section>;
}

export function BlueprintMetric({
  detail,
  label,
  tone = "info",
  value,
}: {
  detail?: string;
  label: string;
  tone?: BlueprintTone;
  value: string;
}) {
  return (
    <article className={["blueprint-metric", tone].join(" ")}>
      <div>
        <i />
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </article>
  );
}

export function BlueprintBadge({
  children,
  tone = "mute",
}: {
  children: ReactNode;
  tone?: BlueprintTone;
}) {
  return <span className={`blueprint-badge ${tone}`}>{children}</span>;
}

export function BlueprintLayout({
  children,
  variant = "two",
}: {
  children: ReactNode;
  variant?: "two" | "three";
}) {
  return <section className={`blueprint-layout ${variant}`}>{children}</section>;
}
