# Iteration One Operations Runbook

This runbook covers local production-style operation for the first complete
Docu Search iteration.

## Services

Start PostgreSQL with pgvector:

```powershell
docker compose up -d postgres
```

Apply database migrations:

```powershell
cd backend
python -m app.cli.migrate_database
```

Start the backend API:

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Optional ingestion worker mode:

```powershell
cd backend
python -m app.cli.run_ingestion_worker
```

Start the frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5174
```

## Required Environment

Backend:

```dotenv
DATABASE_URL=postgresql://docusearch:docusearch@127.0.0.1:55432/docusearch
DATABASE_CONNECT_TIMEOUT_SECONDS=2
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
LOCAL_EMBEDDING_DIMENSIONS=384
INGESTION_RUN_MODE=background
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:120b-cloud
```

Optional hardening:

```dotenv
ADMIN_API_TOKEN=replace-with-a-long-random-secret
API_RATE_LIMIT_PER_MINUTE=120
MAX_UPLOAD_FILES=100
MAX_UPLOAD_FILE_SIZE_BYTES=26214400
LOG_LEVEL=INFO
```

Frontend when admin auth is enabled:

```dotenv
VITE_API_BASE_URL=/api
VITE_ADMIN_TOKEN=replace-with-a-long-random-secret
```

## Verification

Backend tests:

```powershell
cd backend
python -m pytest
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

## Admin Workflows

- Ingestion: `/admin/ingestion`
- Evaluation history: `/admin/evaluation`
- Trace history: `/admin/traces`
- Document inventory, chunk inspection, delete, re-index: `/admin/index`
- Metrics and clear controls: `/admin/ops`

## Backup And Restore

Backup:

```powershell
docker exec docu-search-postgres pg_dump -U docusearch -d docusearch > storage\backups\docusearch.sql
```

Restore:

```powershell
Get-Content storage\backups\docusearch.sql | docker exec -i docu-search-postgres psql -U docusearch -d docusearch
```

## Notes

- The local rate limiter is process-local. Use a Redis-backed limiter for
  horizontally scaled deployment.
- API background tasks are suitable for this local production-style iteration.
  For multi-worker deployment, move ingestion execution to a separate worker
  process backed by a durable queue.
- RAG traces and evaluation runs are intentionally persisted for inspection.
  Clear old traces from `/admin/traces` when needed.
- Chat uses streaming responses from `/chat/ask/stream` and persists the final
  user/assistant messages after generation completes.
