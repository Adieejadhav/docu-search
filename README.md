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

Docker is the main runtime for this project.
The commands below assume GNU Make is available in your terminal.

For a prod-like local stack:

```powershell
make build-run
```

This starts PostgreSQL/pgvector, runs the one-shot migration service, starts the
backend on `http://localhost:8000`, and serves the frontend on
`http://localhost:8080`.

Docker uses `.env.docker`. It contains the database password, exposed ports,
and Ollama connection/model. Other runtime values use defaults from
`docker-compose.yml` and backend config.

The root `.env` is intentionally kept only for local backend debugging. It
points the backend at the Docker-exposed PostgreSQL port on `127.0.0.1:55432`.

Docker commands:

```powershell
make build
make run
make build-run
```

Log commands:

```powershell
make logs-backend
make logs-frontend
make logs-postgres
```

Those map directly to:

```powershell
docker compose --env-file .env.docker build
docker compose --env-file .env.docker up
docker compose --env-file .env.docker up --build
docker compose --env-file .env.docker logs -f backend
docker compose --env-file .env.docker logs -f frontend
docker compose --env-file .env.docker logs -f postgres
```

Docker defaults to `LOG_LEVEL=INFO` so normal app request/startup logs are
visible. Add `LOG_LEVEL=WARNING` to `.env.docker` only when you want quieter
backend logs.

Raw logs include Postgres startup/error logs, frontend proxy/access logs,
Uvicorn startup/error logs, backend request logs, external HTTP logs, and
migrations. Repetitive frontend health-check access logs, Postgres checkpoint
logs, and duplicate Uvicorn access lines are intentionally removed.

The default Docker env expects Ollama on the host at:

```text
http://host.docker.internal:11434
```

## Frontend

The frontend is under `frontend/` and uses the existing backend API paths.

Validate from `frontend/`:

```powershell
npm ci
npm run build
```
