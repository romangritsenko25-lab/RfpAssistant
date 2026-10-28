import json
from datetime import date
from pathlib import Path

import pytest

from rfp.config import Settings
from rfp.eval import dataset
from rfp.eval.judge import judge_answer
from rfp.eval.metrics import EvalRecord, GoldItem, GoldSource, compute_metrics, extraction_rate
from rfp.eval.report import RunInfo, render_report, report_paths, sample_for_review, write_raw
from rfp.eval.runner import run_items
from rfp.llm import LLMReply, LLMUsage
from rfp.models import Answer, Citation, RetrievedChunk

USAGE = LLMUsage(model="gpt-4o-mini", prompt_tokens=100, completion_tokens=50, cost_usd=0.01)


def gold(item_id: str, answerable: bool = True, doc: str = "DOC-1", conflict: bool = False) -> GoldItem:
    return GoldItem(
        id=item_id,
        file="q.xlsx",
        question=f"Question {item_id}?",
        language="en",
        answerable=answerable,
        gold_answer="Reference" if answerable else None,
        sources=[GoldSource(doc_id=doc, section="S")] if answerable else [],
        conflict=conflict,
    )


def answer(item_id: str, status: str = "answered", docs: tuple[str, ...] = ()) -> Answer:
    citations = [Citation(doc_id=d, section="S", snippet="quote text", chunk_id=1) for d in docs]
    return Answer(qid=item_id, text="text", status=status, confidence=0.8, citations=citations)


def record(item: GoldItem, ans: Answer, verdict: str = "unjudged", **extra) -> EvalRecord:
    return EvalRecord(item=item, answer=ans, verdict=verdict, **extra)


def test_metrics_on_synthetic_run() -> None:
    records = [
        record(gold("A1"), answer("A1", docs=("DOC-1",)), "correct", seconds=2, cost_usd=0.01),
        record(gold("A2"), answer("A2", docs=("DOC-9",)), "partial", seconds=4, cost_usd=0.01),
        record(gold("A3"), answer("A3"), "incorrect", seconds=6, cost_usd=0.01),
        record(gold("A4"), answer("A4", "no_data"), "incorrect", seconds=8, cost_usd=0.0),
        record(gold("N1", False), answer("N1", "no_data"), seconds=1, cost_usd=0.0),
        record(gold("N2", False), answer("N2", "answered", docs=("DOC-1",)), seconds=1, cost_usd=0.01),
    ]

    m = compute_metrics(records)

    assert (m.total, m.answerable, m.unanswerable) == (6, 4, 2)
    assert (m.correct, m.partial, m.incorrect, m.unjudged) == (0.25, 0.25, 0.5, 0.0)
    assert m.with_source == 0.5  # A1 and A2 cited
    assert m.supporting_source == 0.5  # of the two cited, only A1 names a gold doc
    assert m.supporting_citations == 0.5
    assert m.refusal_recall == 0.5
    assert m.refusal_precision == 0.5  # no_data given for A4 and N1, only N1 was right
    assert m.retrieval_hit == 0.0
    assert m.total_seconds == 22
    assert m.seconds_per_question == pytest.approx(22 / 6)
    assert m.cost_total_usd == pytest.approx(0.04)
    assert m.cost_per_100_usd == pytest.approx(0.04 / 6 * 100)


def test_retrieval_hit_counts_gold_document_among_retrieved() -> None:
    records = [
        record(gold("A1"), answer("A1"), retrieved_doc_ids=["X", "DOC-1"]),
        record(gold("A2"), answer("A2"), retrieved_doc_ids=["X"]),
    ]

    assert compute_metrics(records).retrieval_hit == 0.5


def test_unknown_cost_makes_totals_unknown() -> None:
    records = [record(gold("A1"), answer("A1"), cost_usd=None)]

    m = compute_metrics(records)

    assert m.cost_total_usd is None
    assert m.cost_per_100_usd is None


def test_empty_run_has_no_division_errors() -> None:
    m = compute_metrics([])

    assert m.total == 0
    assert m.correct == 0.0
    assert m.refusal_precision == 0.0
    assert m.cost_total_usd is None


def test_extraction_rate_ignores_numbering_and_case() -> None:
    gold_questions = ["Is MFA required?", "Where is data stored?", "Never extracted question"]
    extracted = ["is mfa required", "Where is data stored? (see appendix)", "Unrelated text"]

    assert extraction_rate(gold_questions, extracted) == (2, 3)


def test_extraction_rate_empty_extraction() -> None:
    assert extraction_rate(["Question one here"], []) == (0, 1)


def test_sample_is_reproducible_and_bounded() -> None:
    records = [record(gold(f"A{i}"), answer(f"A{i}")) for i in range(30)]

    first = sample_for_review(records)
    second = sample_for_review(records)

    assert len(first) == 10
    assert [r.item.id for r in first] == [r.item.id for r in second]
    assert len(sample_for_review(records[:4])) == 4


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content

    def complete_json(self, system: str, user: str) -> LLMReply:
        return LLMReply(content=self.content, usage=USAGE)


def test_judge_parses_verdict_and_rejects_garbage() -> None:
    item = gold("A1")

    assert judge_answer(FakeLLM('{"verdict": "partial", "reason": "r"}'), "p", item, "t")[:2] == (
        "partial",
        "r",
    )
    assert judge_answer(FakeLLM('{"verdict": "great"}'), "p", item, "t")[0] == "unjudged"
    assert judge_answer(FakeLLM("nope"), "p", item, "t")[0] == "unjudged"


def retrieved(chunk_id: int, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, doc_id="DOC-1", title="T", heading="H", language="en", text=text, score=1.0
    )


def test_run_items_end_to_end_with_fakes(tmp_path: Path) -> None:
    prompt = tmp_path / "answer.md"
    prompt.write_text("system", encoding="utf-8")
    settings = Settings(database_url="postgresql://unused", answer_prompt_path=prompt, _env_file=None)
    answer_json = json.dumps(
        {
            "text": "Yes [1].",
            "status": "answered",
            "confidence": 0.9,
            "citations": [{"fragment": 1, "quote": "MFA is required for all remote access"}],
        }
    )
    items = [gold("A1"), gold("N1", False)]
    chunks = {
        "Question A1?": [retrieved(1, "MFA is required for all remote access.")],
        "Question N1?": [],
    }

    records = run_items(
        items,
        lambda q: chunks[q],
        FakeLLM(answer_json),
        FakeLLM('{"verdict": "correct", "reason": "ok"}'),
        settings,
        "judge prompt",
    )

    assert [r.answer.status for r in records] == ["answered", "no_data"]
    assert records[0].verdict == "correct"
    assert records[0].retrieved_doc_ids == ["DOC-1"]
    assert records[0].prompt_tokens == 100
    assert records[1].verdict == "unjudged"  # unanswerable questions are not judged
    assert compute_metrics(records).refusal_recall == 1.0


def test_answerable_refusal_is_incorrect_without_judge(tmp_path: Path) -> None:
    prompt = tmp_path / "answer.md"
    prompt.write_text("system", encoding="utf-8")
    settings = Settings(database_url="postgresql://unused", answer_prompt_path=prompt, _env_file=None)

    records = run_items([gold("A1")], lambda q: [], FakeLLM("{}"), FakeLLM("not called"), settings, "p")

    assert records[0].verdict == "incorrect"


def test_load_gold_version_is_hash_of_file(tmp_path: Path) -> None:
    line = gold("A1").model_dump_json()
    (tmp_path / "gold.jsonl").write_text(line + "\n", encoding="utf-8")

    items, version = dataset.load_gold(tmp_path)
    (tmp_path / "gold.jsonl").write_text(line + "\n" + gold("A2").model_dump_json() + "\n", encoding="utf-8")
    _, changed = dataset.load_gold(tmp_path)

    assert [i.id for i in items] == ["A1"]
    assert len(version) == 12
    assert version != changed


def test_dev_set_gold_loads_and_extraction_covers_it() -> None:
    folder = dataset.set_dir("dev")
    if not (folder / "gold.jsonl").is_file():
        pytest.skip("dev set is not present")
    items, _ = dataset.load_gold(folder)
    extracted = dataset.extract_set_questions(folder, {i.file for i in items})

    found = total = 0
    for name, questions in extracted.items():
        f, t = extraction_rate([i.question for i in items if i.file == name], [q.text for q in questions])
        found, total = found + f, total + t

    assert total == len(items) == 55
    assert found / total >= 0.95


def test_report_contains_header_metrics_and_sample(tmp_path: Path) -> None:
    records = [
        record(gold("A1"), answer("A1", docs=("DOC-1",)), "correct", cost_usd=0.01),
        record(gold("N1", False), answer("N1", "answered"), cost_usd=0.01),
    ]
    info = RunInfo(
        set_name="dev",
        set_version="abc123def456",
        run_date=date(2026, 10, 28),
        llm_model="gpt-4o-mini",
        judge_model="gpt-4o",
        embedding_model="text-embedding-3-small",
        top_k=5,
        confidence_threshold=0.5,
    )

    text = render_report(info, compute_metrics(records), records, {"q.xlsx": (1, 1)})
    report_path, raw_path = report_paths(tmp_path, info)
    write_raw(raw_path, records)

    assert report_path.name == "quality-2026-10-28-dev.md"
    assert "abc123def456" in text
    assert "gpt-4o-mini" in text
    assert "judge model: `gpt-4o`" in text
    assert "Judge (separate" in text
    assert "| Correct answers | 100.0% | at least 75% |" in text
    assert "- N1: no answer in the set, but status answered" in text
    assert "### A1 (en)" in text
    assert len(raw_path.read_text(encoding="utf-8").splitlines()) == 2
