export type ServiceStatus = "ok" | "degraded";

export interface HealthServiceStatus {
  status: ServiceStatus;
  details: Record<string, unknown>;
}

export interface HealthResponse {
  status: ServiceStatus;
  service: string;
  database: HealthServiceStatus;
  embedding: HealthServiceStatus;
  llm: HealthServiceStatus;
}

export interface DocumentSummary {
  id: string;
  title: string;
  file_name: string;
  file_type: string;
  source_path: string | null;
  parent_chunk_count: number;
  child_chunk_count: number;
  created_at: string | null;
  updated_at: string | null;
  metadata: Record<string, unknown>;
}

export interface DocumentListResponse {
  total: number;
  limit: number;
  offset: number;
  documents: DocumentSummary[];
}

export interface SearchRequest {
  query: string;
  top_k: number;
  file_name?: string;
  file_type?: string;
  document_id?: string;
}

export interface RetrievedChunkResponse {
  rank: number;
  score: number;
  file_name: string | null;
  file_type: string | null;
  source_refs: string[];
  parent_path: string[];
  child_chunk_id: string;
  parent_chunk_id: string;
  child_text: string;
  parent_text: string;
}

export interface SearchResponse {
  query: string;
  embedding_model: string;
  top_k: number;
  results: RetrievedChunkResponse[];
  metadata: Record<string, unknown>;
}

export interface AskResponse {
  query: string;
  answer: string;
  llm_model: string;
  retrieval: SearchResponse;
  citations: Record<string, unknown>[];
}

export interface AdminClearIndexResponse {
  status: "cleared";
  document_count: number;
  parent_chunk_count: number;
  child_chunk_count: number;
}

export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
