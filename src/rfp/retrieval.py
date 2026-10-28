"""Hybrid retrieval: full-text and vector search merged with Reciprocal Rank Fusion."""

import re

import psycopg
from pgvector import Vector

from rfp.config import get_settings
from rfp.embeddings import Embedder
from rfp.models import RetrievedChunk

CANDIDATES_PER_SEARCH = 20
RRF_K = 60


def rrf_fuse(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Merge ranked id lists: each id scores the sum of ``1 / (k + rank)`` (rank from 1) over the lists.

    Returns ``(id, score)`` pairs, best first; ties keep the order of first appearance.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: -pair[1])


def retrieve(
    conn: psycopg.Connection, embedder: Embedder, question: str, k: int | None = None
) -> list[RetrievedChunk]:
    """Return the ``k`` best chunks for ``question`` (default ``retrieval_top_k``).

    Two searches each yield ``CANDIDATES_PER_SEARCH`` candidates: full-text over heading and text
    (the 'simple' configuration, no stemming, as the base mixes ru/kk/en; any question word may
    match, ranked by ``ts_rank``) and cosine similarity of embeddings. ``RetrievedChunk.score`` is
    the Reciprocal Rank Fusion score of the two rankings, not a similarity: it only orders results.
    """
    k = k or get_settings().retrieval_top_k
    terms = re.findall(r"\w+", question)
    if not terms:
        return []
    text_ids = [
        row[0]
        for row in conn.execute(
            """
            SELECT id FROM chunks, to_tsquery('simple', %(query)s) AS q
            WHERE tsv @@ q
            ORDER BY ts_rank(tsv, q) DESC, id
            LIMIT %(n)s
            """,
            {"query": " | ".join(terms), "n": CANDIDATES_PER_SEARCH},
        )
    ]
    [vector] = embedder.embed([question])
    vector_ids = [
        row[0]
        for row in conn.execute(
            "SELECT id FROM chunks ORDER BY embedding <=> %s, id LIMIT %s",
            (Vector(vector), CANDIDATES_PER_SEARCH),
        )
    ]
    fused = rrf_fuse([text_ids, vector_ids])[:k]
    if not fused:
        return []
    rows = conn.execute(
        """
        SELECT c.id, c.doc_id, d.title, c.heading, d.language, d.effective_date, c.text
        FROM chunks c JOIN documents d USING (doc_id)
        WHERE c.id = ANY(%s)
        """,
        ([chunk_id for chunk_id, _ in fused],),
    ).fetchall()
    by_id = {row[0]: row for row in rows}
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            doc_id=by_id[chunk_id][1],
            title=by_id[chunk_id][2],
            heading=by_id[chunk_id][3],
            language=by_id[chunk_id][4],
            effective_date=by_id[chunk_id][5],
            text=by_id[chunk_id][6],
            score=score,
        )
        for chunk_id, score in fused
    ]
