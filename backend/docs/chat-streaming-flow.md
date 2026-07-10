# Chat Streaming Flow

## Non-Streaming Chat

```text
POST /chat/ask
  -> API route
  -> ChatService.ask()
  -> ChatStore.ensure_session()
  -> save user message
  -> retrieve chunks
  -> generate answer with RagAnswerer
  -> record trace
  -> save assistant message
  -> ChatAskResponse
```

## Streaming Chat

```text
POST /chat/ask/stream
  -> API route
  -> ChatService.stream_answer()
  -> yield ChatStreamEvent("session", ...)
  -> retrieve chunks
  -> yield ChatStreamEvent("retrieval", ...)
  -> stream Ollama deltas
  -> yield ChatStreamEvent("delta", ...)
  -> record trace and save assistant message
  -> yield ChatStreamEvent("complete", ...)
```

If an exception occurs during the stream, `ChatService` yields
`ChatStreamEvent("error", ...)`.

## SSE Boundary

Raw SSE strings now live in the API route:

```text
app/api/routes/chat.py
  serialize_sse_events()
  sse_event()
```

`ChatService` yields typed `ChatStreamEvent` objects and no longer emits raw
`event:` or `data:` protocol strings.

Preserved event names:

```text
session
retrieval
delta
complete
error
```
