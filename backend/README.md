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

Background ingestion runs in the API process. No external durable queue is
implemented.

## Docker Notes

The backend runtime services are built from the same backend Dockerfile. Docker
shares cached layers across `migrations` and `backend`.

Useful commands from the repository root:

```powershell
make build
make run
make build-run
make logs-backend
```

Inside Docker, `DATABASE_URL` must point at the Compose service name
`postgres`, not `127.0.0.1`.
