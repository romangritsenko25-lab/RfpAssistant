"""Markdown quality report and raw run dump."""

import json
import random
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from rfp.eval.metrics import EvalRecord, Metrics

SAMPLE_SIZE = 10
SAMPLE_SEED = 20261028


class RunInfo(BaseModel):
    """Run parameters printed in the report header."""

    set_name: str
    set_version: str
    run_date: date
    llm_model: str
    judge_model: str
    embedding_model: str
    top_k: int
    confidence_threshold: float
    limit: int | None = None


def sample_for_review(
    records: list[EvalRecord], size: int = SAMPLE_SIZE, seed: int = SAMPLE_SEED
) -> list[EvalRecord]:
    """Pick a reproducible random sample (fixed seed) for manual checking, in the original order."""
    if len(records) <= size:
        return list(records)
    picked = sorted(random.Random(seed).sample(range(len(records)), size))
    return [records[i] for i in picked]


def report_paths(root: Path, info: RunInfo) -> tuple[Path, Path]:
    stem = f"quality-{info.run_date.isoformat()}-{info.set_name}"
    return root / f"{stem}.md", root / "raw" / f"{stem}.jsonl"


def write_raw(path: Path, records: list[EvalRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(record.model_dump(mode="json"), ensure_ascii=False) for record in records)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(
    info: RunInfo, metrics: Metrics, records: list[EvalRecord], extraction: dict[str, tuple[int, int]]
) -> str:
    """Render the report; thresholds in the table are the acceptance criteria of the terms of reference."""
    found = sum(f for f, _ in extraction.values())
    total = sum(t for _, t in extraction.values())
    refused_ok = round(metrics.refusal_recall * metrics.unanswerable)
    limit_note = f", limited to the first {info.limit}" if info.limit else ""
    lines = [
        f"# Quality report: {info.set_name} set, {info.run_date.isoformat()}",
        "",
        f"- Set: `{info.set_name}`, version (SHA-256 of gold.jsonl, first 12 chars): `{info.set_version}`",
        f"- Questions: {metrics.total} ({metrics.answerable} answerable, "
        f"{metrics.unanswerable} without an answer){limit_note}",
        f"- Answer model: `{info.llm_model}`; judge model: `{info.judge_model}`; "
        f"embeddings: `{info.embedding_model}`",
        f"- Retrieval: top-k {info.top_k}; confidence threshold {info.confidence_threshold}",
        "",
        "## Acceptance metrics",
        "",
        "| Metric | Result | Threshold (terms of reference, section 9) |",
        "|---|---|---|",
        f"| Correct answers | {pct(metrics.correct)} | at least 75% |",
        f"| Partially correct | {pct(metrics.partial)} | not specified |",
        f"| Incorrect answers | {pct(metrics.incorrect)} | at most 10% |",
        f"| Not judged (judge reply invalid) | {pct(metrics.unjudged)} | 0% |",
        f"| Answers with a source | {pct(metrics.with_source)} | at least 95% |",
        f"| Cited answers with a gold document as source | {pct(metrics.supporting_source)} | at least 90% |",
        f"| Citations pointing at a gold document | {pct(metrics.supporting_citations)} | for reference |",
        f"| Refusal recall (`no_data` on unanswerable) | {pct(metrics.refusal_recall)} "
        f"({refused_ok}/{metrics.unanswerable}) | at least 90% (18 of 20) |",
        f"| Refusal precision | {pct(metrics.refusal_precision)} | for reference |",
        f"| Questions found when parsing the source files | {pct(found / total if total else 0.0)} "
        f"({found}/{total}) | at least 95% |",
        f"| Time per question | {metrics.seconds_per_question:.1f} s | 100 questions in 15 min (9 s each) |",
        f"| Retrieval hit (gold document among retrieved) | {pct(metrics.retrieval_hit)} | for reference |",
        "",
        "Accuracy is judged by an LLM against the reference answer; the sample below is for manual "
        "checking. A refusal on an answerable question counts as incorrect. Thresholds apply to the full "
        "100-question test set; a dev set is smaller, so its figures are indicative.",
        "",
        "## Cost and usage",
        "",
        f"- Tokens (answer generation, judge excluded): {metrics.prompt_tokens} prompt, "
        f"{metrics.completion_tokens} completion",
        f"- Cost: {_usd(metrics.cost_total_usd)} total, {_usd(metrics.cost_per_question_usd)} per question, "
        f"{_usd(metrics.cost_per_100_usd)} per 100 questions",
        f"- Judge (separate, not part of the service cost): {metrics.judge_prompt_tokens} prompt, "
        f"{metrics.judge_completion_tokens} completion tokens, {_usd(metrics.judge_cost_total_usd)}",
        f"- Total time: {metrics.total_seconds:.0f} s",
        f"- Citations rejected by the quote check: {metrics.rejected_citations}",
        "- Prices come from a constant table in `rfp/llm.py`; verify them with the provider before quoting.",
        "",
        "## Parsing of source files",
        "",
        *[f"- `{name}`: {f} of {t} questions found" for name, (f, t) in sorted(extraction.items())],
        "",
        "## Answers to review",
        "",
        *_problem_lines(records),
        "",
        f"## Manual sample ({SAMPLE_SIZE} random pairs, seed {SAMPLE_SEED})",
        "",
    ]
    for record in sample_for_review(records):
        lines.extend(_sample_block(record))
    return "\n".join(lines).rstrip() + "\n"


def _usd(value: float | None) -> str:
    return "unknown (model not in price table)" if value is None else f"${value:.4f}"


def _problem_lines(records: list[EvalRecord]) -> list[str]:
    rows = []
    for r in records:
        if r.item.answerable and r.verdict != "correct":
            rows.append(f"- {r.item.id}: verdict {r.verdict}, status {r.answer.status}")
        elif not r.item.answerable and r.answer.status != "no_data":
            rows.append(f"- {r.item.id}: no answer in the set, but status {r.answer.status}")
    return rows or ["- none"]


def _sample_block(record: EvalRecord) -> list[str]:
    item, answer = record.item, record.answer
    sources = ", ".join(f"{c.doc_id} / {c.section}" for c in answer.citations) or "none"
    judge = f"- Judge: {record.verdict}" + (f" ({record.verdict_reason})" if record.verdict_reason else "")
    return [
        f"### {item.id} ({item.language})",
        "",
        f"- Question: {item.question}",
        f"- Answer ({answer.status}, confidence {answer.confidence:.2f}): {answer.text}",
        f"- Cited: {sources}",
        f"- Reference: {item.gold_answer or 'no answer in the knowledge base'}",
        judge,
        "",
    ]
