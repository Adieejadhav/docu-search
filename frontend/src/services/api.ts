import type {
  AdminClearIndexResponse,
  ApiMetricsSnapshot,
  ApiErrorResponse,
  AskResponse,
  ChatAskRequest,
  ChatAskResponse,
  ChatMessageResponse,
  ChatSessionDetail,
  ChatSessionListResponse,
  ChatSessionSummary,
  CreateIngestionJobOptions,
  DocumentChunkListResponse,
  DocumentDeleteResponse,
  DocumentListResponse,
  EvaluationCase,
  EvaluationRunHistoryResponse,
  EvaluationRunRequest,
  EvaluationRunResponse,
  HealthResponse,
  IngestionJob,
  IngestionJobCreateResponse,
  IngestionJobListResponse,
  RagTraceDeleteResponse,
  RagTraceDetail,
  RagTraceListResponse,
  SearchRequest,
  SearchResponse,
} from "./types";

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
export const API_BASE_URL = configuredApiBaseUrl || "/api";
const configuredAdminToken = import.meta.env.VITE_ADMIN_TOKEN?.trim();

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents");
}

export async function getDocumentChunks(
  documentId: string,
): Promise<DocumentChunkListResponse> {
  return request<DocumentChunkListResponse>(
    `/admin/documents/${encodeURIComponent(documentId)}/chunks`,
  );
}

export async function deleteDocument(
  documentId: string,
): Promise<DocumentDeleteResponse> {
  return request<DocumentDeleteResponse>(
    `/admin/documents/${encodeURIComponent(documentId)}`,
    { method: "DELETE" },
  );
}

export async function reindexDocument(
  documentId: string,
): Promise<IngestionJobCreateResponse> {
  return request<IngestionJobCreateResponse>(
    `/admin/documents/${encodeURIComponent(documentId)}/reindex`,
    { method: "POST" },
  );
}

export async function searchDocuments(payload: SearchRequest): Promise<SearchResponse> {
  return request<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify(cleanSearchPayload(payload)),
  });
}

export async function askDocuments(payload: SearchRequest): Promise<AskResponse> {
  return request<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify(cleanSearchPayload(payload)),
  });
}

export async function listChatSessions(): Promise<ChatSessionListResponse> {
  return request<ChatSessionListResponse>("/chat/sessions");
}

export async function createChatSession(
  title?: string,
): Promise<ChatSessionSummary> {
  return request<ChatSessionSummary>("/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export async function getChatSession(sessionId: string): Promise<ChatSessionDetail> {
  return request<ChatSessionDetail>(`/chat/sessions/${encodeURIComponent(sessionId)}`);
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await request<{ status: "deleted"; session_id: string }>(
    `/chat/sessions/${encodeURIComponent(sessionId)}`,
    { method: "DELETE" },
  );
}

export async function askChat(payload: ChatAskRequest): Promise<ChatAskResponse> {
  return request<ChatAskResponse>("/chat/ask", {
    method: "POST",
    body: JSON.stringify(cleanSearchPayload(payload)),
  });
}

export interface ChatStreamHandlers {
  onSession?: (payload: {
    session: ChatSessionSummary;
    user_message: ChatMessageResponse;
  }) => void;
  onRetrieval?: (payload: SearchResponse) => void;
  onDelta?: (text: string) => void;
  onComplete?: (payload: {
    session: ChatSessionSummary;
    assistant_message: ChatMessageResponse;
    trace_id: string;
  }) => void;
  onError?: (error: Error) => void;
}

export async function askChatStream(
  payload: ChatAskRequest,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (configuredAdminToken) {
    headers.set("X-Admin-Token", configuredAdminToken);
  }

  const response = await fetch(`${API_BASE_URL}/chat/ask/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(cleanSearchPayload(payload)),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }
  if (!response.body) {
    throw new Error("STREAM_UNAVAILABLE: Browser did not expose the response stream.");
  }

  await consumeEventStream(response.body, handlers);
}

export async function clearIndex(): Promise<AdminClearIndexResponse> {
  return request<AdminClearIndexResponse>("/admin/index/clear", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}

export async function getApiMetrics(): Promise<ApiMetricsSnapshot> {
  return request<ApiMetricsSnapshot>("/admin/metrics");
}

export async function createIngestionJob(
  options: CreateIngestionJobOptions,
): Promise<IngestionJobCreateResponse> {
  const formData = new FormData();
  for (const file of options.files) {
    formData.append("files", await materializeUploadBlob(file), file.name || "upload");
  }
  formData.set("clear_index", String(options.clear_index));
  formData.set("replace", String(options.replace));
  formData.set("continue_on_error", String(options.continue_on_error));

  return request<IngestionJobCreateResponse>("/admin/ingestion/jobs", {
    method: "POST",
    body: formData,
  });
}

async function materializeUploadBlob(file: File): Promise<Blob> {
  try {
    return new Blob([await file.arrayBuffer()], {
      type: file.type || "application/octet-stream",
    });
  } catch {
    throw new Error(
      `UPLOAD_FILE_READ_FAILED: The browser could not read "${displayUploadFileName(file)}". Choose it again with the file or folder picker.`,
    );
  }
}

function displayUploadFileName(file: File): string {
  return file.webkitRelativePath || file.name || "upload";
}

export async function listIngestionJobs(): Promise<IngestionJobListResponse> {
  return request<IngestionJobListResponse>("/admin/ingestion/jobs");
}

export async function getIngestionJob(jobId: string): Promise<IngestionJob> {
  return request<IngestionJob>(`/admin/ingestion/jobs/${encodeURIComponent(jobId)}`);
}

export async function listEvaluationCases(): Promise<EvaluationCase[]> {
  return request<EvaluationCase[]>("/admin/evaluation/cases");
}

export async function runEvaluation(
  payload: EvaluationRunRequest,
): Promise<EvaluationRunResponse> {
  return request<EvaluationRunResponse>("/admin/evaluation/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listEvaluationRuns(): Promise<EvaluationRunHistoryResponse> {
  return request<EvaluationRunHistoryResponse>("/admin/evaluation/runs");
}

export async function listRagTraces(): Promise<RagTraceListResponse> {
  return request<RagTraceListResponse>("/admin/traces");
}

export async function getRagTrace(traceId: string): Promise<RagTraceDetail> {
  return request<RagTraceDetail>(`/admin/traces/${encodeURIComponent(traceId)}`);
}

export async function clearRagTraces(): Promise<RagTraceDeleteResponse> {
  return request<RagTraceDeleteResponse>("/admin/traces", { method: "DELETE" });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (configuredAdminToken) {
    headers.set("X-Admin-Token", configuredAdminToken);
  }

  const url = `${API_BASE_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers,
    });
  } catch (error) {
    throw new Error(
      [
        `NETWORK_REQUEST_BLOCKED: Could not reach ${url}.`,
        "If this happened during file upload, the browser, an extension, antivirus, or OS file-access policy may have blocked the request before it reached the API.",
        error instanceof Error ? error.message : "",
      ]
        .filter(Boolean)
        .join(" "),
    );
  }

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function consumeEventStream(
  stream: ReadableStream<Uint8Array>,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\r?\n\r?\n/);
    buffer = events.pop() ?? "";
    for (const eventText of events) {
      handleSseEvent(eventText, handlers);
    }
  }

  if (buffer.trim()) {
    handleSseEvent(buffer, handlers);
  }
}

function handleSseEvent(eventText: string, handlers: ChatStreamHandlers) {
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of eventText.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  const rawData = dataLines.join("\n");
  if (!rawData) return;
  const data = JSON.parse(rawData) as Record<string, unknown>;

  if (eventName === "session") {
    handlers.onSession?.(data as {
      session: ChatSessionSummary;
      user_message: ChatMessageResponse;
    });
    return;
  }
  if (eventName === "retrieval") {
    handlers.onRetrieval?.(data as unknown as SearchResponse);
    return;
  }
  if (eventName === "delta") {
    handlers.onDelta?.(String(data.text ?? ""));
    return;
  }
  if (eventName === "complete") {
    handlers.onComplete?.(data as {
      session: ChatSessionSummary;
      assistant_message: ChatMessageResponse;
      trace_id: string;
    });
    return;
  }
  if (eventName === "error") {
    const code = String(data.code ?? "STREAM_ERROR");
    const message = String(data.message ?? "Streaming request failed.");
    handlers.onError?.(new Error(`${code}: ${message}`));
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorResponse;
    return `${payload.code}: ${payload.message}`;
  } catch {
    return `${response.status}: ${response.statusText}`;
  }
}

function cleanSearchPayload(payload: SearchRequest | ChatAskRequest): SearchRequest | ChatAskRequest {
  return {
    query: payload.query.trim(),
    top_k: payload.top_k,
    ...(payload.file_name?.trim() ? { file_name: payload.file_name.trim() } : {}),
    ...(payload.file_type?.trim() ? { file_type: payload.file_type.trim() } : {}),
    ...(payload.document_id?.trim() ? { document_id: payload.document_id.trim() } : {}),
    ...("session_id" in payload && payload.session_id
      ? { session_id: payload.session_id }
      : {}),
  };
}
