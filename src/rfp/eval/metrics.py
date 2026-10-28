"""Acceptance metrics from section 9 of the terms of reference, as pure functions over run records."""

from typing import Literal

from pydantic import BaseModel, Field

from rfp.answering import normalize_text
from rfp.models import Answer

Verdict = Literal["correct", "partial", "incorrect", "unjudged"]


class GoldSource(BaseModel):
    doc_id: str
    section: str


class GoldItem(BaseModel):
    id: str
    file: str
    question: str
    language: str
    answerable: bool
    gold_answer: str | None = None
    sources: list[GoldSource] = Field(default_factory=list)
    conflict: bool = False

    @property
    def source_doc_ids(self) -> set[str]:
        return {source.doc_id for source in self.sources}


class EvalRecord(BaseModel):
    """Everything measured for one question."""

    item: GoldItem
    answer: Answer
    retrieved_doc_ids: list[str] = Field(default_factory=list)
    verdict: Verdict = "unjudged"
    verdict_reason: str = ""
    seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    rejected_citations: int = 0
    judge_prompt_tokens: int = 0
    judge_completion_tokens: int = 0
    judge_cost_usd: float | None = 0.0


class Metrics(BaseModel):
    total: int
    answerable: int
    unanswerable: int
    correct: float
    partial: float
    incorrect: float
    unjudged: float
    with_source: float
    supporting_source: float
    supporting_citations: float
    refusal_recall: float
    refusal_precision: float
    retrieval_hit: float
    rejected_citations: int
    seconds_per_question: float
    total_seconds: float
    prompt_tokens: int
    completion_tokens: int
    cost_total_usd: float | None
    cost_per_question_usd: float | None
    cost_per_100_usd: float | None
    judge_prompt_tokens: int
    judge_completion_tokens: int
    judge_cost_total_usd: float | None


def ratio(part: float, whole: int) -> float:
    """``part / whole`` with 0.0 for an empty denominator."""
    return part / whole if whole else 0.0


def compute_metrics(records: list[EvalRecord]) -> Metrics:
    """Aggregate run records.

    Accuracy shares are over answerable questions; an answerable question the system refused with
    ``no_data`` counts as incorrect without a judge call. ``with_source`` is the share of answerable
    questions whose answer has at least one citation. ``supporting_source`` is the share of those
    cited answers where at least one citation names a gold source document; ``supporting_citations``
    is the same per single citation. Refusal recall is the share of unanswerable questions marked
    ``no_data``; precision is the share of ``no_data`` answers that really had no answer in the set.
    """
    answerable = [r for r in records if r.item.answerable]
    unanswerable = [r for r in records if not r.item.answerable]
    n = len(answerable)

    cited = [r for r in answerable if r.answer.citations]
    supporting = [r for r in cited if _supports(r)]
    all_citations = [c for r in answerable for c in r.answer.citations]
    good_citations = [c for r in answerable for c in r.answer.citations if c.doc_id in r.item.source_doc_ids]

    refused = [r for r in records if r.answer.status == "no_data"]
    correct_refusals = [r for r in unanswerable if r.answer.status == "no_data"]
    hits = [r for r in answerable if r.item.source_doc_ids & set(r.retrieved_doc_ids)]

    costs = [r.cost_usd for r in records]
    cost_total = sum(c for c in costs if c is not None) if records and None not in costs else None
    cost_per_question = cost_total / len(records) if cost_total is not None else None
    total_seconds = sum(r.seconds for r in records)
    judge_costs = [r.judge_cost_usd for r in records]
    judge_cost_total = sum(c for c in judge_costs if c is not None) if None not in judge_costs else None

    return Metrics(
        total=len(records),
        answerable=n,
        unanswerable=len(unanswerable),
        correct=ratio(_count(answerable, "correct"), n),
        partial=ratio(_count(answerable, "partial"), n),
        incorrect=ratio(_count(answerable, "incorrect"), n),
        unjudged=ratio(_count(answerable, "unjudged"), n),
        with_source=ratio(len(cited), n),
        supporting_source=ratio(len(supporting), len(cited)),
        supporting_citations=ratio(len(good_citations), len(all_citations)),
        refusal_recall=ratio(len(correct_refusals), len(unanswerable)),
        refusal_precision=ratio(len(correct_refusals), len(refused)),
        retrieval_hit=ratio(len(hits), n),
        rejected_citations=sum(r.rejected_citations for r in records),
        seconds_per_question=ratio(total_seconds, len(records)),
        total_seconds=total_seconds,
        prompt_tokens=sum(r.prompt_tokens for r in records),
        completion_tokens=sum(r.completion_tokens for r in records),
        cost_total_usd=cost_total,
        cost_per_question_usd=cost_per_question,
        cost_per_100_usd=cost_per_question * 100 if cost_per_question is not None else None,
        judge_prompt_tokens=sum(r.judge_prompt_tokens for r in records),
        judge_completion_tokens=sum(r.judge_completion_tokens for r in records),
        judge_cost_total_usd=judge_cost_total,
    )


def extraction_rate(gold_questions: list[str], extracted_texts: list[str]) -> tuple[int, int]:
    """Count gold questions found among extracted texts; return ``(found, total)``.

    A gold question is found when its normalised text contains, or is contained in, a normalised
    extracted text, so a dropped number prefix or a trimmed tail does not count as a miss.
    """
    extracted = [normalize_text(text) for text in extracted_texts]
    found = 0
    for question in gold_questions:
        needle = normalize_text(question)
        if any(needle in text or (text and text in needle) for text in extracted):
            found += 1
    return found, len(gold_questions)


def _count(records: list[EvalRecord], verdict: Verdict) -> int:
    return sum(1 for r in records if r.verdict == verdict)


def _supports(record: EvalRecord) -> bool:
    return any(c.doc_id in record.item.source_doc_ids for c in record.answer.citations)
