"""Index knowledge-base files into the database and keep the index in sync with a folder."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import psycopg
from pgvector import Vector

from rfp.chunking import chunk_document
from rfp.documents import SUPPORTED_SUFFIXES, parse_document
from rfp.embeddings import Embedder

log = logging.getLogger(__name__)

IndexStatus = Literal["indexed", "unchanged", "removed", "failed"]


@dataclass(frozen=True)
class IndexResult:
    path: Path
    doc_id: str | None
    status: IndexStatus
    chunks: int = 0
    error: str | None = None


def index_file(conn: psycopg.Connection, embedder: Embedder, path: Path) -> IndexResult:
    """Index one file; skip it if its sha256 is unchanged, otherwise replace the document's chunks."""
    path = path.resolve()
    doc_id: str | None = None
    try:
        doc = parse_document(path)
        doc_id = doc.doc_id
        row = conn.execute("SELECT sha256 FROM documents WHERE doc_id = %s", (doc_id,)).fetchone()
        if row and row[0] == doc.sha256:
            conn.execute("UPDATE documents SET source_path = %s WHERE doc_id = %s", (doc.source_path, doc_id))
            return IndexResult(path, doc_id, "unchanged")
        chunks = chunk_document(doc)
        vectors = embedder.embed([f"{c.heading}\n{c.text}" for c in chunks])
        with conn.transaction():
            conn.execute(
                """
                INSERT INTO documents (doc_id, title, language, effective_date, source_path, sha256)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (doc_id) DO UPDATE SET
                    title = EXCLUDED.title, language = EXCLUDED.language,
                    effective_date = EXCLUDED.effective_date, source_path = EXCLUDED.source_path,
                    sha256 = EXCLUDED.sha256, indexed_at = now()
                """,
                (doc_id, doc.title, doc.language, doc.effective_date, doc.source_path, doc.sha256),
            )
            conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (doc_id, ord, heading, text, embedding) VALUES (%s, %s, %s, %s, %s)",
                    [
                        (doc_id, c.order, c.heading, c.text, Vector(vector))
                        for c, vector in zip(chunks, vectors, strict=True)
                    ],
                )
        return IndexResult(path, doc_id, "indexed", chunks=len(chunks))
    except Exception as exc:
        log.warning("Failed to index %s: %s", path, exc)
        return IndexResult(path, doc_id, "failed", error=f"{type(exc).__name__}: {exc}")


def index_folder(conn: psycopg.Connection, embedder: Embedder, folder: Path) -> list[IndexResult]:
    """Index every supported file under ``folder`` and delete documents whose files have disappeared."""
    folder = folder.resolve()
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    results = [index_file(conn, embedder, path) for path in files]
    present = {str(p) for p in files}
    stored = conn.execute("SELECT doc_id, source_path FROM documents ORDER BY doc_id").fetchall()
    for doc_id, source_path in stored:
        if source_path in present or not Path(source_path).is_relative_to(folder):
            continue
        conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        results.append(IndexResult(Path(source_path), doc_id, "removed"))
    return results


def watch_folder(
    conn_factory: Callable[[], psycopg.Connection],
    embedder: Embedder,
    folder: Path,
    interval_s: float,
    stop: threading.Event | None = None,
) -> None:
    """Poll ``folder`` every ``interval_s`` seconds and sync it into the database until ``stop`` is set."""
    stop = stop or threading.Event()
    while not stop.is_set():
        try:
            with conn_factory() as conn:
                results = index_folder(conn, embedder, folder)
            changed = [r for r in results if r.status != "unchanged"]
            if changed:
                log.info("Synced %s: %s", folder, ", ".join(f"{r.path.name}={r.status}" for r in changed))
        except Exception:
            log.exception("Sync of %s failed; retrying in %s s", folder, interval_s)
        stop.wait(interval_s)
