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

-- Web service tables.

CREATE TABLE IF NOT EXISTS users (
    id            bigserial PRIMARY KEY,
    username      text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    is_admin      boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- One uploaded questionnaire. The file itself is kept here so the answers can be exported into it later.
CREATE TABLE IF NOT EXISTS jobs (
    id          bigserial PRIMARY KEY,
    filename    text NOT NULL,
    source_file bytea NOT NULL,
    params      jsonb NOT NULL DEFAULT '{}'::jsonb,
    status      text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'done', 'failed')),
    total       integer NOT NULL DEFAULT 0,
    error       text,
    created_by  text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    started_at  timestamptz,
    finished_at timestamptz
);

-- One question of a job with its drafted answer. model_* keep the model's draft; text/status are the
-- current (possibly reviewed) values. status 'pending' means the question has not been processed yet.
CREATE TABLE IF NOT EXISTS job_items (
    job_id       bigint NOT NULL REFERENCES jobs (id) ON DELETE CASCADE,
    qid          text NOT NULL,
    ord          integer NOT NULL,
    question     jsonb NOT NULL,
    status       text NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'answered', 'approved', 'edited', 'needs_review', 'no_data')),
    text         text NOT NULL DEFAULT '',
    confidence   double precision NOT NULL DEFAULT 0,
    citations    jsonb NOT NULL DEFAULT '[]'::jsonb,
    model_text   text,
    model_status text,
    note         text,
    reviewed_by  text,
    reviewed_at  timestamptz,
    PRIMARY KEY (job_id, qid)
);

-- Reviewed answers saved to the knowledge base; each one is the document REF-<id> with a single chunk.
CREATE TABLE IF NOT EXISTS reference_answers (
    id         bigserial PRIMARY KEY,
    job_id     bigint,
    qid        text,
    question   text NOT NULL,
    answer     text NOT NULL,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (job_id, qid)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          bigserial PRIMARY KEY,
    ts          timestamptz NOT NULL DEFAULT now(),
    username    text,
    action      text NOT NULL,
    object_type text,
    object_id   text,
    details     jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS llm_log (
    id                bigserial PRIMARY KEY,
    ts                timestamptz NOT NULL DEFAULT now(),
    job_id            bigint,
    qid               text,
    question          text NOT NULL,
    chunks            jsonb NOT NULL DEFAULT '[]'::jsonb,
    answer_text       text,
    status            text,
    model             text,
    prompt_tokens     integer,
    completion_tokens integer,
    cost_usd          double precision,
    latency_s         double precision,
    duration_s        double precision,
    error             text
);

CREATE INDEX IF NOT EXISTS audit_log_ts_idx ON audit_log (ts DESC, id DESC);
CREATE INDEX IF NOT EXISTS llm_log_ts_idx ON llm_log (ts DESC, id DESC);
CREATE INDEX IF NOT EXISTS llm_log_job_idx ON llm_log (job_id);
