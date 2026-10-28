from pathlib import Path

import psycopg
import pytest

from rfp.ingest import index_folder
from rfp.retrieval import retrieve, rrf_fuse
from tests.conftest import FakeEmbedder


def test_rrf_scores_and_order():
    fused = rrf_fuse([[1, 2, 3], [3, 1]], k=60)
    scores = dict(fused)
    assert scores[1] == pytest.approx(1 / 61 + 1 / 62)
    assert scores[3] == pytest.approx(1 / 63 + 1 / 61)
    assert [i for i, _ in fused] == [1, 3, 2]


def test_rrf_ties_keep_first_appearance_and_empty_input():
    assert [i for i, _ in rrf_fuse([[7], [8]])] == [7, 8]
    assert rrf_fuse([[], []]) == []


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    (tmp_path / "vpn.md").write_text(
        "# VPN policy\n\n## Remote access\n\nEmployees connect through the corporate gateway.\n", "utf-8"
    )
    (tmp_path / "backup.md").write_text(
        "# Backup\n\n## Retention\n\nBackups are kept for 35 days. Policy code RTO-4417 applies.\n", "utf-8"
    )
    (tmp_path / "kz.md").write_text("# Қауіпсіздік\n\n## Құпия сөз\n\nҚұпия сөз кемінде 12 таңба.\n", "utf-8")
    return tmp_path


@pytest.mark.db
def test_exact_term_found_by_full_text(db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, kb: Path):
    index_folder(db_conn, fake_embedder, kb)
    found = retrieve(db_conn, fake_embedder, "RTO-4417", k=3)
    assert found[0].doc_id == "backup"
    assert found[0].heading == "Retention"
    assert found[0].score > 0


@pytest.mark.db
def test_kazakh_term_found(db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, kb: Path):
    index_folder(db_conn, fake_embedder, kb)
    assert retrieve(db_conn, fake_embedder, "құпия", k=1)[0].doc_id == "kz"


@pytest.mark.db
def test_found_by_meaning_without_shared_words(db_conn: psycopg.Connection, kb: Path):
    target = FakeEmbedder().embed(["Remote access\nEmployees connect through the corporate gateway."])[0]
    embedder = FakeEmbedder(overrides={"how do I work from home?": target})
    index_folder(db_conn, embedder, kb)
    # No word of the question appears in the chunk, so only the vector search can find it.
    found = retrieve(db_conn, embedder, "how do I work from home?", k=1)
    assert found[0].doc_id == "vpn"


@pytest.mark.db
def test_k_limits_results_and_blank_question(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, kb: Path
):
    index_folder(db_conn, fake_embedder, kb)
    assert len(retrieve(db_conn, fake_embedder, "backups policy days", k=2)) == 2
    assert retrieve(db_conn, fake_embedder, "  ?! ", k=2) == []


@pytest.mark.db
def test_empty_base_returns_nothing(db_conn: psycopg.Connection, fake_embedder: FakeEmbedder):
    assert retrieve(db_conn, fake_embedder, "anything", k=3) == []
