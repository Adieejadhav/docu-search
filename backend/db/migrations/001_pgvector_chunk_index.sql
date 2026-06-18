CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    source_path TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS parent_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    source_block_ids JSONB NOT NULL,
    source_refs JSONB NOT NULL,
    parent_path JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS child_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    parent_chunk_id TEXT NOT NULL REFERENCES parent_chunks(id) ON DELETE CASCADE,
    child_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    source_block_ids JSONB NOT NULL,
    source_refs JSONB NOT NULL,
    parent_path JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS child_embeddings (
    child_chunk_id TEXT PRIMARY KEY REFERENCES child_chunks(id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimensions INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parent_chunks_document_id
    ON parent_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_child_chunks_document_id
    ON child_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_child_chunks_parent_chunk_id
    ON child_chunks(parent_chunk_id);

CREATE INDEX IF NOT EXISTS idx_documents_file_name
    ON documents(file_name);

CREATE INDEX IF NOT EXISTS idx_documents_file_type
    ON documents(file_type);

CREATE INDEX IF NOT EXISTS idx_child_embeddings_embedding_hnsw
    ON child_embeddings
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_child_chunks_text_fts
    ON child_chunks
    USING gin (to_tsvector('english', text));

CREATE INDEX IF NOT EXISTS idx_parent_chunks_text_fts
    ON parent_chunks
    USING gin (to_tsvector('english', text));

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_paths JSONB NOT NULL DEFAULT '[]'::jsonb,
    file_count INTEGER NOT NULL DEFAULT 0,
    discovered_input_files INTEGER NOT NULL DEFAULT 0,
    parsed_document_count INTEGER NOT NULL DEFAULT 0,
    chunked_document_count INTEGER NOT NULL DEFAULT 0,
    parent_chunk_count INTEGER NOT NULL DEFAULT 0,
    child_chunk_count INTEGER NOT NULL DEFAULT 0,
    indexed_child_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    timings_ms JSONB NOT NULL DEFAULT '{}'::jsonb,
    events JSONB NOT NULL DEFAULT '[]'::jsonb,
    error_code TEXT,
    error_message TEXT,
    error_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    options JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status_created
    ON ingestion_jobs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS rag_traces (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    llm_model TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    top_k INTEGER NOT NULL,
    result_count INTEGER NOT NULL,
    retrieval_ms DOUBLE PRECISION NOT NULL,
    answer_ms DOUBLE PRECISION NOT NULL,
    total_ms DOUBLE PRECISION NOT NULL,
    retrieval_json JSONB NOT NULL,
    citations JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_traces_created
    ON rag_traces(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rag_traces_query_fts
    ON rag_traces
    USING gin (to_tsvector('english', query || ' ' || answer));

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    trace_id TEXT,
    llm_model TEXT,
    latency_ms DOUBLE PRECISION,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
    ON chat_sessions(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages(session_id, created_at);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY,
    top_k INTEGER NOT NULL,
    include_answers BOOLEAN NOT NULL,
    total_cases INTEGER NOT NULL,
    passed_cases INTEGER NOT NULL,
    failed_cases INTEGER NOT NULL,
    source_hit_rate DOUBLE PRECISION NOT NULL,
    answer_term_pass_rate DOUBLE PRECISION,
    mean_total_ms DOUBLE PRECISION NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_created
    ON evaluation_runs(created_at DESC);
