-- Idempotent schema, applied at startup by rfp.db.apply_schema.
-- {dim} is replaced with Settings.embedding_dim. Append new tables below; keep every statement re-runnable.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    doc_id         text PRIMARY KEY,
    title          text NOT NULL,
    language       text NOT NULL,
    effective_date date,
    source_path    text NOT NULL,
    sha256         text NOT NULL,
    indexed_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id        bigserial PRIMARY KEY,
    doc_id    text NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    ord       integer NOT NULL,
    heading   text NOT NULL,
    text      text NOT NULL,
    embedding vector({dim}) NOT NULL,
    tsv       tsvector GENERATED ALWAYS AS (to_tsvector('simple', heading || ' ' || text)) STORED,
    UNIQUE (doc_id, ord)
);

CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
