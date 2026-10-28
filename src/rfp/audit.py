"""Audit log (who did what) and model request log (question, fragments, answer, tokens, cost, time)."""

from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from rfp.answering import GeneratedAnswer
from rfp.models import RetrievedChunk


class ActionEntry(BaseModel):
    id: int
    ts: datetime
    username: str | None
    action: str = Field(description="Dotted action name, e.g. 'login', 'answer.edit', 'job.export'")
    object_type: str | None
    object_id: str | None
    details: dict


class FragmentRef(BaseModel):
    chunk_id: int
    doc_id: str
    score: float


class ModelRequestEntry(BaseModel):
    id: int
    ts: datetime
    job_id: int | None
    qid: str | None
    question: str
    fragments: list[FragmentRef]
    answer_text: str | None
    status: str | None
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None = Field(description="None when the model has no known price")
    latency_s: float | None = Field(description="Time of the model call")
    duration_s: float | None = Field(description="Retrieval plus model call")
    error: str | None


def log_action(
    conn: psycopg.Connection,
    username: str | None,
    action: str,
    object_type: str | None = None,
    object_id: str | int | None = None,
    details: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (username, action, object_type, object_id, details)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (username, action, object_type, None if object_id is None else str(object_id), Jsonb(details or {})),
    )


def log_model_request(
    conn: psycopg.Connection,
    *,
    job_id: int | None,
    qid: str | None,
    question: str,
    chunks: list[RetrievedChunk],
    generated: GeneratedAnswer | None,
    duration_s: float,
    error: str | None = None,
) -> None:
    """Record one question's pass through retrieval and the model; ``generated`` is None on failure."""
    usage = generated.usage if generated else None
    fragments = [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "score": c.score} for c in chunks]
    conn.execute(
        """
        INSERT INTO llm_log (job_id, qid, question, chunks, answer_text, status, model, prompt_tokens,
                             completion_tokens, cost_usd, latency_s, duration_s, error)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            job_id,
            qid,
            question,
            Jsonb(fragments),
            generated.answer.text if generated else None,
            generated.answer.status if generated else None,
            usage.model if usage else None,
            usage.prompt_tokens if usage else None,
            usage.completion_tokens if usage else None,
            usage.cost_usd if usage else None,
            usage.latency_s if usage else None,
            duration_s,
            error,
        ),
    )


def list_actions(conn: psycopg.Connection, limit: int, offset: int) -> tuple[list[ActionEntry], int]:
    """Newest first; returns the page and the total number of entries."""
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT * FROM audit_log ORDER BY ts DESC, id DESC LIMIT %s OFFSET %s", (limit, offset)
        ).fetchall()
        total = cur.execute("SELECT count(*) AS n FROM audit_log").fetchone()
    return [ActionEntry.model_validate(row) for row in rows], total["n"] if total else 0


def list_model_requests(
    conn: psycopg.Connection, limit: int, offset: int, job_id: int | None = None
) -> tuple[list[ModelRequestEntry], int]:
    """Newest first, optionally of one job; returns the page and the total number of entries."""
    where, params = ("WHERE job_id = %s", [job_id]) if job_id is not None else ("", [])
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            f"SELECT * FROM llm_log {where} ORDER BY ts DESC, id DESC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        ).fetchall()
        total = cur.execute(f"SELECT count(*) AS n FROM llm_log {where}", params).fetchone()
    entries = [ModelRequestEntry.model_validate({**row, "fragments": row["chunks"]}) for row in rows]
    return entries, total["n"] if total else 0
