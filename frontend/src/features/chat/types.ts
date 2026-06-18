import type { RetrievedChunkResponse } from "../../services/types";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: RetrievedChunkResponse[];
  latencyMs?: number;
  model?: string;
  traceId?: string;
}
