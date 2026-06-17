import type {
  AdminClearIndexResponse,
  ApiErrorResponse,
  AskResponse,
  DocumentListResponse,
  HealthResponse,
  SearchRequest,
  SearchResponse,
} from "./types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function getDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>("/documents");
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

export async function clearIndex(): Promise<AdminClearIndexResponse> {
  return request<AdminClearIndexResponse>("/admin/index/clear", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  return response.json() as Promise<T>;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorResponse;
    return `${payload.code}: ${payload.message}`;
  } catch {
    return `${response.status}: ${response.statusText}`;
  }
}

function cleanSearchPayload(payload: SearchRequest): SearchRequest {
  return {
    query: payload.query.trim(),
    top_k: payload.top_k,
    ...(payload.file_name?.trim() ? { file_name: payload.file_name.trim() } : {}),
    ...(payload.file_type?.trim() ? { file_type: payload.file_type.trim() } : {}),
    ...(payload.document_id?.trim() ? { document_id: payload.document_id.trim() } : {}),
  };
}
