import threading
from pathlib import Path

import psycopg
import pytest

from rfp.db import connect
from rfp.ingest import index_file, index_folder, watch_folder
from tests.conftest import FakeEmbedder

pytestmark = pytest.mark.db


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "one.md").write_text("# One\n\n## A\n\nalpha text\n\n## B\n\nbeta text\n", "utf-8")
    (kb / "two.md").write_text("# Two\n\n## C\n\ngamma text\n", "utf-8")
    (kb / "notes.txt").write_text("not supported", "utf-8")
    return kb


def counts(conn: psycopg.Connection) -> tuple[int, int]:
    docs = conn.execute("SELECT count(*) FROM documents").fetchone()
    chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()
    assert docs and chunks
    return docs[0], chunks[0]


def test_index_folder_then_again_is_unchanged(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, folder: Path
):
    first = index_folder(db_conn, fake_embedder, folder)
    assert sorted((r.doc_id, r.status) for r in first) == [("one", "indexed"), ("two", "indexed")]
    assert counts(db_conn) == (2, 3)
    calls = fake_embedder.calls
    second = index_folder(db_conn, fake_embedder, folder)
    assert {r.status for r in second} == {"unchanged"}
    assert fake_embedder.calls == calls
    assert counts(db_conn) == (2, 3)


def test_changed_file_is_reindexed_without_duplicates(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, folder: Path
):
    index_folder(db_conn, fake_embedder, folder)
    (folder / "one.md").write_text("# One\n\n## A\n\nonly delta now\n", "utf-8")
    result = index_file(db_conn, fake_embedder, folder / "one.md")
    assert (result.status, result.chunks) == ("indexed", 1)
    assert counts(db_conn) == (2, 2)
    texts = [r[0] for r in db_conn.execute("SELECT text FROM chunks WHERE doc_id = 'one'")]
    assert texts == ["only delta now"]


def test_removed_file_is_deleted_from_database(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, folder: Path
):
    index_folder(db_conn, fake_embedder, folder)
    (folder / "two.md").unlink()
    results = index_folder(db_conn, fake_embedder, folder)
    assert [(r.doc_id, r.status) for r in results if r.status == "removed"] == [("two", "removed")]
    assert counts(db_conn) == (1, 2)


def test_documents_outside_the_folder_are_kept(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, folder: Path, tmp_path: Path
):
    other = tmp_path / "other"
    other.mkdir()
    (other / "far.md").write_text("# Far\n\n## X\n\nelsewhere\n", "utf-8")
    index_folder(db_conn, fake_embedder, other)
    index_folder(db_conn, fake_embedder, folder)
    assert counts(db_conn)[0] == 3


def test_broken_file_does_not_stop_the_folder(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, folder: Path
):
    (folder / "broken.docx").write_bytes(b"not a zip")
    results = {r.path.name: r for r in index_folder(db_conn, fake_embedder, folder)}
    assert results["broken.docx"].status == "failed"
    assert results["broken.docx"].error
    assert results["one.md"].status == "indexed"
    assert counts(db_conn)[0] == 2


def test_failed_embedding_keeps_the_old_version(
    db_conn: psycopg.Connection, fake_embedder: FakeEmbedder, folder: Path
):
    index_file(db_conn, fake_embedder, folder / "one.md")

    class Broken(FakeEmbedder):
        def embed(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("API down")

    (folder / "one.md").write_text("# One\n\n## A\n\nnew text\n", "utf-8")
    result = index_file(db_conn, Broken(), folder / "one.md")
    assert result.status == "failed"
    assert "API down" in (result.error or "")
    assert counts(db_conn) == (1, 2)


def test_watch_folder_syncs_until_stopped(
    db_conn: psycopg.Connection, test_database_url: str, fake_embedder: FakeEmbedder, folder: Path
):
    stop = threading.Event()
    thread = threading.Thread(
        target=watch_folder, args=(lambda: connect(test_database_url), fake_embedder, folder, 0.05, stop)
    )
    thread.start()
    try:
        for _ in range(100):
            if counts(db_conn)[0] == 2:
                break
            stop.wait(0.1)
        assert counts(db_conn)[0] == 2
    finally:
        stop.set()
        thread.join(timeout=10)
    assert not thread.is_alive()
