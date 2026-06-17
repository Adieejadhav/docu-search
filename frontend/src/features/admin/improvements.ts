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
  items.push("Add HTTP ingestion jobs with progress persistence.");
  items.push("Batch embeddings and bulk-insert vectors for faster indexing.");
  items.push("Add auth, tenant isolation, and answer quality evaluation.");
  return items.slice(0, 6);
}
