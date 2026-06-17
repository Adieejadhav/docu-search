export function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}

export function PerfMetric({ label, value }: { label: string; value?: number }) {
  return (
    <div className="perf-metric">
      <span>{label}</span>
      <strong>{value === undefined ? "-" : `${value}ms`}</strong>
    </div>
  );
}
