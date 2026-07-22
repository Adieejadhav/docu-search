# Docu Search

Full-stack RAG document-search application.

## Backend

The backend is a FastAPI modular monolith. See
`backend/docs/backend-overview.md` and `backend/docs/current-limitations.md`.

Validate from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Docker

Docker is an additional supported run mode; local development still works.

For a prod-like local stack:

```powershell
Copy-Item .env.docker.example .env.docker
docker compose --env-file .env.docker up --build -d
```

This starts PostgreSQL/pgvector, runs the one-shot migration service, starts the
backend on `http://localhost:8000`, and serves the frontend on
`http://localhost:8080`.

Check status and follow focused logs with:

```powershell
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker logs -f --tail=100 backend
docker compose --env-file .env.docker logs -f --tail=100 frontend
docker compose --env-file .env.docker logs -f --tail=100 migrations
```

Use `docker compose --env-file .env.docker logs -f --tail=100` only when you
want all service logs together.

Compose normally appends replica indexes such as `backend-1`. This stack sets
fixed container names like `docu-search-backend` for more predictable logs.
Use `--no-log-prefix` when you want only the raw one-line application log:

```powershell
docker compose --env-file .env.docker logs -f --tail=100 --no-log-prefix backend
docker logs -f --tail=100 docu-search-backend
```

Docker defaults to `LOG_LEVEL=INFO` so normal app request/startup logs are
visible. Set `LOG_LEVEL=WARNING` in `.env.docker` only when you want quieter
backend logs.

Combined Docker logs are organized but still visible:

- Containers use stable names such as `docu-search-backend`.
- Frontend access logs use a compact one-line key/value format for API requests.
- Health checks are hidden from frontend logs.
- Migration output is a single summary line.

The default Docker env expects Ollama on the host at:

```text
http://host.docker.internal:11434
```

Run the polling ingestion worker with:

```powershell
docker compose --env-file .env.docker --profile worker up --build -d
docker compose --env-file .env.docker logs -f --tail=100 worker
```

## Frontend

The frontend is under `frontend/` and uses the existing backend API paths.

Validate from `frontend/`:

```powershell
npm ci
npm run build
```
