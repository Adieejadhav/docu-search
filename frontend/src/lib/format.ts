import type { DocumentSummary } from "../services/types";

export function messageFromError(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

export function scorePercent(score: number): string {
  return `${Math.round(score * 1000) / 10}%`;
}

export function summarizeDocuments(documents: DocumentSummary[]) {
  return documents.reduce(
    (summary, document) => ({
      parentChunks: summary.parentChunks + document.parent_chunk_count,
      childChunks: summary.childChunks + document.child_chunk_count,
    }),
    { parentChunks: 0, childChunks: 0 },
  );
}

export function elapsedMs(start: number): number {
  return Math.round((performance.now() - start) * 10) / 10;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
