"""PostgreSQL access: connections with pgvector support and the idempotent schema."""

import contextlib
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from rfp.config import get_settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_LOCK_ID = 727_001  # serializes concurrent apply_schema calls (app and workers starting together)


def connect(url: str | None = None) -> psycopg.Connection:
    """Open an autocommit connection; transactions are opened explicitly with ``conn.transaction()``."""
    conn = psycopg.connect(url or get_settings().database_url, autocommit=True)
    # Without the extension the type is unknown; apply_schema installs it and registers the type.
    with contextlib.suppress(psycopg.ProgrammingError):
        register_vector(conn)
    return conn


def apply_schema(conn: psycopg.Connection, embedding_dim: int | None = None) -> None:
    """Create missing tables and indexes. Fails if the stored vectors have another size."""
    dim = embedding_dim or get_settings().embedding_dim
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (SCHEMA_LOCK_ID,))
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
        existing = _existing_dim(conn)
        if existing is not None and existing != dim:
            raise RuntimeError(
                f"The database stores {existing}-dimensional embeddings but EMBEDDING_DIM is {dim}. "
                "Recreate the database and reindex the knowledge base."
            )
        conn.execute(SCHEMA_PATH.read_text("utf-8").replace("{dim}", str(dim)).encode())


def _existing_dim(conn: psycopg.Connection) -> int | None:
    row = conn.execute(
        "SELECT atttypmod FROM pg_attribute WHERE attrelid = to_regclass('chunks') AND attname = 'embedding'"
    ).fetchone()
    return row[0] if row else None
