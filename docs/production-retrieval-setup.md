# Production Retrieval Setup

This project uses PostgreSQL with pgvector for persistent retrieval storage,
local sentence-transformers embeddings, and Ollama for answer generation.

The production retrieval path is:

```text
chunks.json -> BAAI/bge-small-en-v1.5 -> PostgreSQL/pgvector -> parent-child retrieval -> Ollama answer
```

## Environment

Create `.env` from `.env.example` if it does not already exist.

```powershell
Copy-Item .env.example .env
```

The backend loads the repo-level `.env` automatically. You do not need manual
shell environment variables for normal local testing.

Required values:

```text
DATABASE_URL=postgresql://docusearch:docusearch@127.0.0.1:55432/docusearch
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
LOCAL_EMBEDDING_DIMENSIONS=384
LOCAL_EMBEDDING_DEVICE=cpu
LOCAL_EMBEDDING_BATCH_SIZE=64
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b-cloud
OLLAMA_TEMPERATURE=0
```

## Start PostgreSQL

```powershell
docker compose up -d postgres
```

## Install Backend Dependencies

```powershell
cd C:\docu-search\backend
python -m pip install -e .[dev]
```

The first embedding run downloads `BAAI/bge-small-en-v1.5` through
sentence-transformers and then reuses the local cache.

## Configure Ollama

```powershell
ollama signin
ollama pull gpt-oss:120b-cloud
```

Keep Ollama running on `http://localhost:11434`.

The local Docker PostgreSQL service is published on host port `55432` to avoid
conflicts with a system PostgreSQL install on `5432`.

## Build Chunks

```powershell
python -m app.cli.chunk_documents "..\storage\rag_robust_format_test_corpus.normalized.json" --output-json "..\storage\rag_robust_format_test_corpus.chunks.json"
```

## End-to-End Ingestion

Use this when you want one command to parse source files, normalize them, create
parent-child chunks, embed child chunks, and upsert everything into pgvector.

```powershell
python -m app.cli.ingest_documents "<source-documents-folder>" --recursive --clear-index --chunks-output-json "..\storage\rag_robust_format_test_corpus.chunks.json"
```

## Index Chunks

Use this lower-level command when you already have a chunk JSON artifact and
only want to re-index it.

```powershell
python -m app.cli.index_chunks "..\storage\rag_robust_format_test_corpus.chunks.json" --clear
```

## Query Retrieval Only

```powershell
python -m app.cli.query_index "satellite mode exception 14 days" --top-k 5 --show-parent
```

## Ask With RAG Answer Generation

```powershell
python -m app.cli.ask_index "Which policy mentions the 14-day satellite-mode exception?" --top-k 5 --show-context
```

## Notes

- The pgvector table is created for `LOCAL_EMBEDDING_DIMENSIONS=384`.
- Recreate or migrate the index before changing embedding dimensions.
- If you previously created a `1536`-dimension index, clear the Docker volume or create a migration before re-indexing.
- The committed SQL schema is in `backend/db/migrations/001_pgvector_chunk_index.sql`.
