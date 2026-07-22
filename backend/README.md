# Docu Search Backend

FastAPI backend for document ingestion, search, chat, and grounded RAG answers.

## Validation

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -c "from app.main import app; print('application import successful')"
```

## Architecture

The runtime flow is:

```text
API endpoint -> Service -> RAG/Ingestion workflow -> Repository -> Integration
```

Start with:

- `docs/backend-overview.md`
- `docs/current-limitations.md`

Background ingestion is process-local in `background` mode and queued for the
polling worker in `worker` mode. No external durable queue is implemented.

## Docker Notes

The backend runtime services are built from the same backend Dockerfile. Docker
shares cached layers across `migrations`, `backend`, and the optional `worker`.

Useful commands from the repository root:

```powershell
docker compose --env-file .env.docker build backend
docker compose --env-file .env.docker run --rm migrations
docker compose --env-file .env.docker up --build -d backend
docker compose --env-file .env.docker logs -f --tail=100 backend
docker compose --env-file .env.docker --profile worker up -d worker
docker compose --env-file .env.docker logs -f --tail=100 worker
```

Inside Docker, `DATABASE_URL` must point at the Compose service name
`postgres`, not `127.0.0.1`.
