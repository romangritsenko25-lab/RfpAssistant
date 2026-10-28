"""Knowledge base management: list, upload (with indexing), delete and re-synchronise documents."""

import logging
from datetime import date, datetime
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from rfp.audit import log_action
from rfp.documents import SUPPORTED_SUFFIXES
from rfp.embeddings import Embedder
from rfp.ingest import IndexStatus, index_file, index_folder
from rfp.services.errors import InvalidInputError, NotFoundError
from rfp.services.references import is_reference_doc

log = logging.getLogger(__name__)


class DocumentInfo(BaseModel):
    doc_id: str
    title: str
    language: str
    effective_date: date | None
    filename: str | None = Field(description="File name in the knowledge base; None for reviewed answers")
    kind: str = Field(description="'file' or 'reference' (a reviewed answer saved from a job)")
    indexed_at: datetime
    chunks: int


class IndexOutcome(BaseModel):
    doc_id: str | None
    filename: str
    status: IndexStatus
    chunks: int = 0
    error: str | None = None


def list_documents(conn: psycopg.Connection) -> list[DocumentInfo]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            """
            SELECT d.doc_id, d.title, d.language, d.effective_date, d.source_path, d.indexed_at,
                   count(c.id) AS chunks
            FROM documents d LEFT JOIN chunks c USING (doc_id)
            GROUP BY d.doc_id ORDER BY d.doc_id
            """
        ).fetchall()
    documents = []
    for row in rows:
        source = row.pop("source_path")
        reference = source.startswith("reference://")
        documents.append(
            DocumentInfo(
                **row,
                filename=None if reference else Path(source).name,
                kind="reference" if reference else "file",
            )
        )
    return documents


def upload_document(
    conn: psycopg.Connection, embedder: Embedder, kb_dir: Path, username: str, filename: str, data: bytes
) -> IndexOutcome:
    """Save the file into ``kb_dir`` and index it; on failure the previous file state is restored."""
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise InvalidInputError(
            f"Unsupported file type '{suffix}'; use {', '.join(sorted(SUPPORTED_SUFFIXES))}."
        )
    if not data:
        raise InvalidInputError("The file is empty.")
    if is_reference_doc(Path(name).stem.upper()):
        raise InvalidInputError("File names starting with 'REF-' are reserved for reviewed answers.")
    kb_dir.mkdir(parents=True, exist_ok=True)
    target = kb_dir / name
    previous = target.read_bytes() if target.exists() else None
    target.write_bytes(data)
    result = index_file(conn, embedder, target)
    if result.status == "failed":
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.write_bytes(previous)
        raise InvalidInputError(f"Cannot index '{name}': {result.error}")
    log_action(
        conn,
        username,
        "document.upload",
        "document",
        result.doc_id,
        {"filename": name, "status": result.status, "chunks": result.chunks},
    )
    return IndexOutcome(doc_id=result.doc_id, filename=name, status=result.status, chunks=result.chunks)


def delete_document(conn: psycopg.Connection, kb_dir: Path, username: str, doc_id: str) -> None:
    """Remove the document from the index and its file from ``kb_dir`` (or folder sync re-adds it)."""
    row = conn.execute("SELECT source_path FROM documents WHERE doc_id = %s", (doc_id,)).fetchone()
    if row is None:
        raise NotFoundError(f"Document {doc_id} not found.")
    source = row[0]
    with conn.transaction():
        conn.execute("DELETE FROM documents WHERE doc_id = %s", (doc_id,))
        if source.startswith("reference://"):
            conn.execute(
                "DELETE FROM reference_answers WHERE id = %s", (int(source.removeprefix("reference://")),)
            )
        log_action(conn, username, "document.delete", "document", doc_id, {})
    path = Path(source)
    if not source.startswith("reference://") and path.is_relative_to(kb_dir.resolve()):
        path.unlink(missing_ok=True)


def reindex(conn: psycopg.Connection, embedder: Embedder, kb_dir: Path, username: str) -> list[IndexOutcome]:
    """Synchronise the index with ``kb_dir`` now (unchanged files are skipped by their hash)."""
    kb_dir.mkdir(parents=True, exist_ok=True)
    results = index_folder(conn, embedder, kb_dir)
    outcomes = [
        IndexOutcome(doc_id=r.doc_id, filename=r.path.name, status=r.status, chunks=r.chunks, error=r.error)
        for r in results
    ]
    counts = {
        status: sum(o.status == status for o in outcomes) for status in ("indexed", "removed", "failed")
    }
    log_action(conn, username, "kb.reindex", "kb", None, counts)
    return outcomes
