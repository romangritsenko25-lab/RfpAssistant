"""The whole generated knowledge base through the indexer (run with ``-m kb`` and TEST_DATABASE_URL)."""

from pathlib import Path

import psycopg
import pytest

from rfp.ingest import index_folder
from rfp.retrieval import retrieve
from tests.conftest import FakeEmbedder

KB = Path(__file__).resolve().parents[1] / "data" / "kb"

pytestmark = [
    pytest.mark.kb,
    pytest.mark.db,
    pytest.mark.skipif(not (KB / "manifest.json").exists(), reason="data/kb has not been built"),
]


def test_whole_knowledge_base_is_indexed(db_conn: psycopg.Connection, fake_embedder: FakeEmbedder):
    results = index_folder(db_conn, fake_embedder, KB)
    assert [(r.path.name, r.error) for r in results if r.status == "failed"] == []
    assert sum(r.status == "indexed" for r in results) == 40
    assert retrieve(db_conn, fake_embedder, "backup retention", k=3)
