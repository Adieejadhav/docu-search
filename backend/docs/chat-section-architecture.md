# Chat Section Architecture

This document explains how the chat section works after the UI optimization pass.

## Current Chat UX Target

The chat route is now treated as its own workspace:

- Left sidebar: chat history only.
- Sidebar action: new chat.
- Sidebar bottom: account/profile/settings/sign-in controls.
- Center: conversation thread.
- Bottom: ChatGPT-style composer.
- Assistant message: answer plus inline citation links.
- No right-side citation panel.

The admin app shell is intentionally not used on `/chat`; admin keeps its own
layout and will be optimized separately.

## Frontend Flow

Main file:

```text
frontend/src/features/chat/ChatPanel.tsx
```

API client:

```text
frontend/src/services/api.ts
```

When the chat page loads:

1. `ChatPanel` calls `listChatSessions()`.
2. Frontend sends `GET /chat/sessions`.
3. Backend returns saved sessions ordered by latest update.
4. If there is an existing session and the current thread is empty, the frontend loads the latest session with `GET /chat/sessions/{session_id}`.

When the user asks a question:

1. The composer submits the trimmed question.
2. `ChatPanel` calls `askChatStream()`.
3. Frontend sends `POST /chat/ask/stream`.
4. Backend returns Server-Sent Events.
5. Frontend appends the user message when the `session` event arrives.
6. Frontend adds a temporary assistant message with `model: "streaming"`.
7. Frontend attaches retrieved sources when the `retrieval` event arrives.
8. Frontend appends answer text as each `delta` event arrives.
9. Frontend replaces the temporary assistant message with the persisted assistant message when the `complete` event arrives.
10. Frontend refreshes the session list so the sidebar reflects the latest title/update time.

## Chat Ask Payload

Streaming endpoint:

```http
POST /chat/ask/stream
Content-Type: application/json
```

Payload:

```json
{
  "query": "Which policy mentions the 14-day satellite-mode exception?",
  "top_k": 5,
  "file_name": "optional exact file name",
  "file_type": "optional file type such as md",
  "document_id": "optional document id",
  "session_id": "optional existing session id"
}
```

Frontend currently sends:

```json
{
  "query": "user question",
  "top_k": 5,
  "session_id": "only when continuing an existing chat"
}
```

## Streaming Response Events

The response content type is:

```text
text/event-stream
```

### `session`

Emitted after the backend creates or finds the chat session and stores the user
message.

```json
{
  "session": {
    "id": "session-id",
    "title": "Question or existing title",
    "message_count": 1,
    "created_at": "2026-06-19T10:00:00Z",
    "updated_at": "2026-06-19T10:00:00Z"
  },
  "user_message": {
    "id": "message-id",
    "session_id": "session-id",
    "role": "user",
    "content": "Question text",
    "trace_id": null,
    "llm_model": null,
    "latency_ms": null,
    "sources": [],
    "created_at": "2026-06-19T10:00:00Z"
  }
}
```

### `retrieval`

Emitted after vector/full-text retrieval completes.

```json
{
  "query": "Question text",
  "embedding_model": "local-sentence-transformers-BAAI/bge-small-en-v1.5-384d",
  "top_k": 5,
  "results": [
    {
      "rank": 1,
      "score": 0.91,
      "document_id": "document-id",
      "file_name": "source.md",
      "file_type": "md",
      "source_refs": ["lines 10-14"],
      "parent_path": ["Policy", "Security"],
      "child_chunk_id": "child-id",
      "parent_chunk_id": "parent-id",
      "child_text": "Matched child text",
      "parent_text": "Expanded parent context"
    }
  ],
  "metadata": {}
}
```

`document_id` was added so chat citations can open the original indexed source file.

### `delta`

Emitted for each streamed LLM text fragment.

```json
{
  "text": "partial answer text"
}
```

### `complete`

Emitted after the backend stores the final assistant message and RAG trace.

```json
{
  "session": "ChatSessionSummary",
  "assistant_message": {
    "id": "message-id",
    "session_id": "session-id",
    "role": "assistant",
    "content": "Final answer text",
    "trace_id": "trace-id",
    "llm_model": "ollama-gpt-oss:120b-cloud",
    "latency_ms": 1234.5,
    "sources": ["RetrievedChunkResponse[]"],
    "created_at": "2026-06-19T10:00:00Z"
  },
  "trace_id": "trace-id"
}
```

### `error`

Emitted if retrieval, LLM streaming, trace writing, or message persistence fails.

```json
{
  "code": "ERROR_CODE",
  "message": "Error message"
}
```

The frontend restores the question in the composer so the user can retry.

## Backend Flow

Main route:

```text
backend/app/api/routes/chat.py::ask_chat_stream
```

Generator:

```text
backend/app/api/routes/chat.py::stream_chat_answer
```

Dependency chain:

```text
get_chunk_index()
  -> PgVectorChunkIndex
  -> LocalSentenceTransformerEmbeddingProvider
  -> PostgreSQL/pgvector

get_rag_answerer()
  -> RagAnswerer
  -> OllamaChatClient

get_rag_trace_store()
  -> RagTraceStore

get_chat_store()
  -> ChatStore
```

Step-by-step backend behavior:

1. `ChatStore.ensure_session()` either loads the existing session or creates a new one.
2. `ChatStore.add_message()` stores the user message.
3. Backend emits `session`.
4. `PgVectorChunkIndex.retrieve()` embeds the query and runs hybrid vector plus lexical retrieval.
5. Backend emits `retrieval`.
6. `RagAnswerer.build_messages()` creates the grounded prompt from retrieved parent context.
7. `OllamaChatClient.stream()` streams answer deltas from Ollama.
8. Backend emits one `delta` event for each answer fragment.
9. Backend joins all deltas into final answer text.
10. `RagTraceStore.record_trace()` stores the full retrieval/answer trace.
11. `ChatStore.add_message()` stores the assistant message with trace id, model, latency, and sources.
12. Backend emits `complete`.

## How Chat History Is Saved

Database tables:

```text
chat_sessions
chat_messages
rag_traces
```

`chat_sessions` stores:

```text
id
title
created_at
updated_at
```

`chat_messages` stores:

```text
id
session_id
role
content
trace_id
llm_model
latency_ms
sources
created_at
```

Important behavior:

- A new session starts as `"New chat"` or the first question title.
- When a message is added, `chat_sessions.updated_at` is updated.
- If the title is `"New chat"`, the first user message becomes the session title.
- Assistant messages store their retrieved sources in `sources` JSONB.
- Assistant messages link to their full trace through `trace_id`.

This means the saved chat history is not just text. It includes:

- User question.
- Assistant answer.
- Model used.
- Latency.
- Source chunks.
- Trace id for deep admin inspection.

## How History Should Evolve Next

The current database model is enough for local iteration, but the next hardening
pass should add:

- Real user id on `chat_sessions`.
- Authentication-backed profile identity.
- Session rename endpoint.
- Session archive/delete distinction.
- Message-level error records for failed generations.
- Optional conversation summary for long chats.
- Pagination for messages inside very long sessions.

## Citation File Opening

The chat UI now renders retrieved sources as inline citation links inside the
assistant message.

Citation link format:

```text
[1] source.md
```

Click behavior:

```text
GET /documents/{document_id}/source
```

Backend file route:

```text
backend/app/api/routes/documents.py::open_document_source
```

The route:

1. Looks up the indexed document by `document_id`.
2. Reads the stored `source_path`.
3. Verifies that the source file still exists on disk.
4. Returns the file inline using `FileResponse`.

If a saved old chat message does not have `document_id` in its stored source
JSON, its citation chip is disabled because there is no safe source-file route
to open.

## Related Environment Variables

```text
DATABASE_URL
LOCAL_EMBEDDING_MODEL
LOCAL_EMBEDDING_DIMENSIONS
LOCAL_EMBEDDING_DEVICE
LOCAL_EMBEDDING_BATCH_SIZE
HYBRID_VECTOR_WEIGHT
HYBRID_LEXICAL_WEIGHT
HYBRID_PHRASE_WEIGHT
OLLAMA_HOST
OLLAMA_MODEL
OLLAMA_TEMPERATURE
API_RATE_LIMIT_PER_MINUTE
```
