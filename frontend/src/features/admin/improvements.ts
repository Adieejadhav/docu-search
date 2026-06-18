import type {
  DocumentListResponse,
  HealthResponse,
  SearchResponse,
} from "../../services/types";

export function buildImprovementAreas(
  health: HealthResponse | null,
  documents: DocumentListResponse | null,
  searchResult: SearchResponse | null,
) {
  const items: string[] = [];
  if (!documents?.total) items.push("Run ingestion before retrieval testing.");
  if (health?.database.status === "degraded") items.push("Resolve pgvector/database health.");
  if (searchResult && searchResult.results.length === 0) {
    items.push("Tune chunking, filters, or query wording for better recall.");
  }
  items.push("Tune hybrid retrieval weights using evaluation history.");
  items.push("Move rate limiting and job claiming to Redis for multi-node deployment.");
  items.push("Add tenant-aware user accounts before external deployment.");
  items.push("Batch embeddings and bulk-insert vectors for faster indexing.");
  return items.slice(0, 6);
}
