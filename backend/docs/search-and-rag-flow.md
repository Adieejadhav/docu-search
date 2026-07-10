# Search And RAG Flow

## Search

```text
POST /search
  -> API route
  -> SearchService.search()
  -> PgVectorChunkIndex.retrieve()
  -> embedding provider embeds query
  -> PgVectorSearch returns vector candidates
  -> LexicalSearch returns full-text candidates
  -> HybridSearchRanker merges and reranks candidates
  -> SearchResponse is mapped from RetrievalResult
```

Search behavior remains hybrid vector plus PostgreSQL full-text search. Default
weights remain vector `0.62`, lexical `0.30`, and phrase `0.08`.

## One-Shot Ask

```text
POST /ask
  -> SearchService.ask()
  -> PgVectorChunkIndex.retrieve()
  -> RagAnswerer.answer()
  -> RagContextBuilder builds context text
  -> RagPromptBuilder builds system and user messages
  -> AnswerGenerator calls OllamaChatClient
  -> CitationValidator extracts citation payloads
  -> RagTraceStore records trace
  -> AskResponse
```

`RagAnswerer` is still the compatibility facade, but the RAG responsibilities
are now separated into smaller components.

## Integration Boundaries

```text
app.integrations.search.pgvector_search
  Vector candidate SQL.

app.integrations.search.lexical_search
  PostgreSQL full-text and phrase candidate SQL.

app.integrations.search.hybrid_search
  Candidate merging, weighting, phrase overlap, and deterministic ordering.

app.integrations.embeddings.sentence_transformer
  sentence-transformers provider.

app.integrations.llm.ollama
  Ollama chat and streaming client.
```
