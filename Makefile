.PHONY: test db-up db-down db-logs ingest-corpus index-corpus query-corpus

test:
	cd backend && python -m pytest

db-up:
	docker compose up -d postgres

db-down:
	docker compose down

db-logs:
	docker compose logs -f postgres

ingest-corpus:
	@if [ -z "$(SOURCE_DIR)" ]; then echo "Set SOURCE_DIR to the raw source document folder."; exit 1; fi
	cd backend && python -m app.cli.ingest_documents "$(SOURCE_DIR)" --recursive --clear-index --chunks-output-json "..\storage\rag_robust_format_test_corpus.chunks.json"

index-corpus:
	cd backend && python -m app.cli.index_chunks "..\storage\rag_robust_format_test_corpus.chunks.json" --clear

query-corpus:
	cd backend && python -m app.cli.query_index "satellite mode exception 14 days" --top-k 5 --show-parent
