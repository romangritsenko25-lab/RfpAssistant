import psycopg
import pytest

from rfp.db import apply_schema
from tests.conftest import FAKE_DIM

pytestmark = pytest.mark.db


def test_apply_schema_twice(db_conn: psycopg.Connection):
    apply_schema(db_conn, FAKE_DIM)
    apply_schema(db_conn, FAKE_DIM)
    tables = {r[0] for r in db_conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
    assert {"documents", "chunks"} <= tables


def test_indexes_exist(db_conn: psycopg.Connection):
    rows = db_conn.execute("SELECT indexdef FROM pg_indexes WHERE tablename = 'chunks'").fetchall()
    defs = " ".join(r[0] for r in rows)
    assert "USING gin (tsv)" in defs
    assert "USING hnsw (embedding vector_cosine_ops)" in defs


def test_changed_dimension_is_a_clear_error(db_conn: psycopg.Connection):
    with pytest.raises(RuntimeError, match="Recreate the database and reindex"):
        apply_schema(db_conn, FAKE_DIM * 2)


def test_deleting_a_document_cascades_to_chunks(db_conn: psycopg.Connection):
    db_conn.execute("INSERT INTO documents VALUES ('d', 't', 'en', NULL, 'p', 'h', now())")
    db_conn.execute(
        "INSERT INTO chunks (doc_id, ord, heading, text, embedding) VALUES ('d', 0, 'h', 't', %s::vector)",
        (str([0.1] * FAKE_DIM),),
    )
    db_conn.execute("DELETE FROM documents WHERE doc_id = 'd'")
    assert db_conn.execute("SELECT count(*) FROM chunks").fetchone() == (0,)
