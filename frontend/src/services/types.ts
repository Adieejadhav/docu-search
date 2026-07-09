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

export interface DocumentChunkSummary {
  child_chunk_id: string;
  parent_chunk_id: string;
  child_index: number;
  parent_index: number;
  child_text: string;
  parent_text: string;
  child_token_count: number;
  parent_token_count: number;
  source_refs: string[];
  parent_path: string[];
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface DocumentChunkListResponse {
  document: DocumentSummary;
  total: number;
  limit: number;
  offset: number;
  chunks: DocumentChunkSummary[];
}

export interface DocumentDeleteResponse {
  status: "deleted";
  document_id: string;
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
  document_id?: string | null;
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

export type PipelineNodeStage = "validate" | "parse" | "chunk" | "embed" | "index";

export interface PipelineNodeTestResponse {
  stage: PipelineNodeStage;
  status: "completed";
  duration_ms: number;
  summary: Record<string, unknown>;
  preview: Array<Record<string, unknown>>;
}

export interface AskResponse {
  query: string;
  answer: string;
  llm_model: string;
  retrieval: SearchResponse;
  citations: Record<string, unknown>[];
  trace_id: string | null;
}

export interface AdminClearIndexResponse {
  status: "cleared";
  document_count: number;
  parent_chunk_count: number;
  child_chunk_count: number;
}

export interface AdminOverviewHealth {
  status: ServiceStatus;
  database_status: ServiceStatus;
  embedding_model: string;
  llm_model: string;
  llm_host: string;
}

export interface AdminOverviewIndexStats {
  document_count: number;
  parent_chunk_count: number;
  child_chunk_count: number;
  vector_count: number;
  readiness_percent: number;
}

export interface AdminOverviewQueryCounts {
  total: number;
  today: number;
  month: number;
  year: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
}

export interface AdminOverviewIngestionJobs {
  total: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  last_completed_at: string | null;
}

export interface AdminOverviewRisk {
  status: "ok" | "attention";
  warning_count: number;
  reasons: string[];
}

export interface AdminOverviewRecentTrace {
  id: string;
  query: string;
  status: "success";
  result_count: number;
  retrieval_ms: number;
  answer_ms: number;
  total_ms: number;
  llm_model: string;
  created_at: string;
}

export interface AdminOverviewRecentJob {
  id: string;
  status: IngestionJobStatus;
  source_kind: string;
  file_count: number;
  parsed_document_count: number;
  indexed_child_count: number;
  failure_count: number;
  duration_ms: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface AdminOverviewResponse {
  health: AdminOverviewHealth;
  index: AdminOverviewIndexStats;
  queries: AdminOverviewQueryCounts;
  ingestion_jobs: AdminOverviewIngestionJobs;
  risk: AdminOverviewRisk;
  recent_traces: AdminOverviewRecentTrace[];
  recent_jobs: AdminOverviewRecentJob[];
}

export type IngestionJobStatus = "queued" | "running" | "completed" | "failed";

export interface IngestionJobEvent {
  stage: string;
  status: string;
  message: string;
  path: string | null;
  duration_ms: number | null;
  metadata: Record<string, unknown>;
  timestamp: string | null;
}

export interface IngestionJob {
  id: string;
  status: IngestionJobStatus;
  source_kind: string;
  source_paths: string[];
  file_count: number;
  discovered_input_files: number;
  parsed_document_count: number;
  chunked_document_count: number;
  parent_chunk_count: number;
  child_chunk_count: number;
  indexed_child_count: number;
  failure_count: number;
  timings_ms: Record<string, number>;
  events: IngestionJobEvent[];
  error_code: string | null;
  error_message: string | null;
  error_details: Record<string, unknown>;
  options: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface IngestionJobCreateResponse {
  job: IngestionJob;
}

export interface IngestionJobListResponse {
  total: number;
  limit: number;
  offset: number;
  jobs: IngestionJob[];
}

export interface CreateIngestionJobOptions {
  files: File[];
  clear_index: boolean;
  replace: boolean;
  continue_on_error: boolean;
}

export interface RagTraceSummary {
  id: string;
  query: string;
  answer: string;
  llm_model: string;
  embedding_model: string;
  top_k: number;
  result_count: number;
  retrieval_ms: number;
  answer_ms: number;
  total_ms: number;
  created_at: string;
}

export interface RagTraceDetail extends RagTraceSummary {
  retrieval: SearchResponse;
  citations: Record<string, unknown>[];
  metadata: Record<string, unknown>;
}

export interface RagTraceListResponse {
  total: number;
  limit: number;
  offset: number;
  traces: RagTraceSummary[];
}

export interface RagTraceDeleteResponse {
  status: "deleted";
  deleted_count: number;
}

export interface ApiMetricsSnapshot {
  total_count: number;
  success_count: number;
  failure_count: number;
  success_by_operation: Record<string, number>;
  failure_by_operation: Record<string, number>;
  failure_by_code: Record<string, number>;
  total_duration_ms_by_operation: Record<string, number>;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageResponse {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  trace_id: string | null;
  llm_model: string | null;
  latency_ms: number | null;
  sources: RetrievedChunkResponse[];
  created_at: string;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessageResponse[];
}

export interface ChatSessionListResponse {
  total: number;
  limit: number;
  offset: number;
  sessions: ChatSessionSummary[];
}

export interface ChatAskRequest extends SearchRequest {
  session_id?: string;
}

export interface ChatAskResponse {
  session: ChatSessionSummary;
  user_message: ChatMessageResponse;
  assistant_message: ChatMessageResponse;
  answer: AskResponse;
}

export interface ApiErrorResponse {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}
