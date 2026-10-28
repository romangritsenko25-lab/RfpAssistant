"""Reference answers: reviewed answers saved into the knowledge base so that later questions find them.

Storage: a reviewed answer becomes an ordinary document with ``doc_id = REF-<id>`` (``id`` from the
``reference_answers`` table) holding one chunk, ``Question: ...`` followed by ``Answer: ...``, with
its own embedding, in the same ``documents``/``chunks`` tables as the files. Hybrid retrieval therefore
finds it like any other fragment, and a citation shows the heading "Reviewed answer" as its source.
Saving the same job question again replaces the document's chunk. ``source_path`` is
``reference://<id>``, which never lies inside KB_DIR, so folder sync leaves these documents alone.
"""

import hashlib
from datetime import date

import psycopg
from pgvector import Vector

from rfp.audit import log_action
from rfp.documents.language import detect_language
from rfp.embeddings import Embedder
from rfp.services.errors import ConflictError, NotFoundError

REFERENCE_PREFIX = "REF-"
REFERENCE_HEADING = "Reviewed answer"
TITLE_QUESTION_CHARS = 80


def is_reference_doc(doc_id: str) -> bool:
    return doc_id.startswith(REFERENCE_PREFIX)


def save_reference_answer(
    conn: psycopg.Connection, embedder: Embedder, job_id: int, qid: str, username: str
) -> str:
    """Store the current text of a reviewed (approved or edited) answer as a reference; returns its doc_id."""
    row = conn.execute(
        "SELECT question ->> 'text', text, status FROM job_items WHERE job_id = %s AND qid = %s",
        (job_id, qid),
    ).fetchone()
    if row is None:
        raise NotFoundError(f"Question {qid} not found in job {job_id}.")
    question, answer, status = row
    if status not in ("approved", "edited"):
        raise ConflictError("Only an approved or edited answer can be saved as a reference.")

    text = f"Question: {question}\nAnswer: {answer}"
    [vector] = embedder.embed([f"{REFERENCE_HEADING}\n{text}"])
    title = f"{REFERENCE_HEADING}: {question[:TITLE_QUESTION_CHARS]}"
    with conn.transaction():
        ref_id = conn.execute(
            """
            INSERT INTO reference_answers (job_id, qid, question, answer, created_by)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (job_id, qid) DO UPDATE SET
                question = EXCLUDED.question, answer = EXCLUDED.answer,
                created_by = EXCLUDED.created_by, created_at = now()
            RETURNING id
            """,
            (job_id, qid, question, answer, username),
        ).fetchone()[0]
        doc_id = f"{REFERENCE_PREFIX}{ref_id}"
        conn.execute(
            """
            INSERT INTO documents (doc_id, title, language, effective_date, source_path, sha256)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO UPDATE SET
                title = EXCLUDED.title, language = EXCLUDED.language,
                effective_date = EXCLUDED.effective_date, sha256 = EXCLUDED.sha256, indexed_at = now()
            """,
            (
                doc_id,
                title,
                detect_language(text),
                date.today(),
                f"reference://{ref_id}",
                hashlib.sha256(text.encode()).hexdigest(),
            ),
        )
        conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
        conn.execute(
            "INSERT INTO chunks (doc_id, ord, heading, text, embedding) VALUES (%s, 0, %s, %s, %s)",
            (doc_id, REFERENCE_HEADING, text, Vector(vector)),
        )
        log_action(conn, username, "reference.save", "document", doc_id, {"job_id": job_id, "qid": qid})
    return doc_id
