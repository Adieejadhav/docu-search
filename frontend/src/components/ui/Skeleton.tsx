export function Skeleton({
  count = 1,
  compact,
}: {
  count?: number;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "skeleton-stack compact" : "skeleton-stack"} aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <span className="skeleton-line" key={index} />
      ))}
    </div>
  );
}
