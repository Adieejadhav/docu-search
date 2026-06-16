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
