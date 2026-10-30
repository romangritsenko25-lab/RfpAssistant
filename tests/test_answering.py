import json
from datetime import date
from pathlib import Path

import pytest

from rfp.answering import (
    answer_question,
    format_fragments,
    normalize_text,
    parse_model_json,
    quote_in_text,
)
from rfp.config import Settings
from rfp.llm import LLMReply, LLMUsage
from rfp.models import Location, Question, RetrievedChunk

USAGE = LLMUsage(model="gpt-4o-mini", prompt_tokens=100, completion_tokens=20, cost_usd=0.001)


class FakeLLM:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> LLMReply:
        self.calls.append((system, user))
        return LLMReply(content=self.content, usage=USAGE)


def reply(**fields) -> str:
    base = {"text": "Backups run daily [1].", "status": "answered", "confidence": 0.9, "citations": []}
    return json.dumps({**base, **fields})


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    prompt = tmp_path / "answer.md"
    prompt.write_text("SYSTEM PROMPT", encoding="utf-8")
    return Settings(
        database_url="postgresql://unused",
        answer_prompt_path=prompt,
        confidence_threshold=0.5,
        _env_file=None,
    )


def chunk(chunk_id: int, text: str, doc_id: str = "DOC-1", heading: str = "Backups") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        doc_id=doc_id,
        title="Policy",
        heading=heading,
        language="en",
        effective_date=date(2026, 1, 1),
        text=text,
        score=0.5,
    )


def question(text: str = "How often are backups made?") -> Question:
    return Question(qid="q1", text=text, location=Location())


CHUNKS = [
    chunk(10, "Backups of production databases are made every day at 02:00.\nCopies are kept for 35 days."),
    chunk(11, "Restore tests are run quarterly.", doc_id="DOC-2", heading="Testing"),
]


def test_valid_answer_keeps_verified_citation(settings: Settings) -> None:
    quote = "Backups of production databases are made every day"
    llm = FakeLLM(reply(citations=[{"fragment": 1, "quote": quote}]))

    result = answer_question(question(), CHUNKS, llm, settings)

    assert result.answer.status == "answered"
    assert result.answer.citations[0].doc_id == "DOC-1"
    assert result.answer.citations[0].section == "Backups"
    assert result.answer.citations[0].snippet == quote
    assert result.answer.citations[0].chunk_id == 10
    assert result.usage == USAGE
    assert result.rejected_citations == 0
    assert llm.calls[0][0] == "SYSTEM PROMPT"
    assert "[2] Policy | section: Testing | effective: 2026-01-01" in llm.calls[0][1]


def test_no_chunks_means_no_data_without_model_call(settings: Settings) -> None:
    llm = FakeLLM(reply())

    result = answer_question(question("Как часто делаются резервные копии?"), [], llm, settings)

    assert result.answer.status == "no_data"
    assert "нет данных" in result.answer.text
    assert result.usage is None
    assert llm.calls == []


def test_invented_quote_is_dropped_and_answer_needs_review(settings: Settings) -> None:
    llm = FakeLLM(
        reply(citations=[{"fragment": 1, "quote": "Backups are encrypted with a quantum-safe cipher"}])
    )

    result = answer_question(question(), CHUNKS, llm, settings)

    assert result.answer.status == "needs_review"
    assert result.answer.citations == []
    assert result.rejected_citations == 1


def test_fragment_number_outside_the_list_is_rejected(settings: Settings) -> None:
    quote = "Restore tests are run quarterly"
    cites = [
        {"fragment": 3, "quote": quote},
        {"fragment": 0, "quote": quote},
        {"fragment": "x", "quote": quote},
    ]

    result = answer_question(question(), CHUNKS, FakeLLM(reply(citations=cites)), settings)

    assert result.answer.status == "needs_review"
    assert result.rejected_citations == 3


def test_good_citation_survives_next_to_bad_one(settings: Settings) -> None:
    cites = [
        {"fragment": 2, "quote": "restore TESTS are run   quarterly."},
        {"fragment": 1, "quote": "Restore tests are run quarterly"},
    ]

    result = answer_question(question(), CHUNKS, FakeLLM(reply(citations=cites)), settings)

    assert result.answer.status == "answered"
    assert [c.chunk_id for c in result.answer.citations] == [11]
    assert result.rejected_citations == 1


def test_low_confidence_needs_review(settings: Settings) -> None:
    cites = [{"fragment": 2, "quote": "Restore tests are run quarterly"}]

    result = answer_question(question(), CHUNKS, FakeLLM(reply(confidence=0.3, citations=cites)), settings)

    assert result.answer.status == "needs_review"
    assert len(result.answer.citations) == 1


def test_model_no_data_drops_citations(settings: Settings) -> None:
    cites = [{"fragment": 2, "quote": "Restore tests are run quarterly"}]
    llm = FakeLLM(reply(status="no_data", text="No data.", citations=cites, confidence=0.2))

    result = answer_question(question(), CHUNKS, llm, settings)

    assert result.answer.status == "no_data"
    assert result.answer.citations == []


def test_conflict_status_from_model_is_kept(settings: Settings) -> None:
    cites = [{"fragment": 1, "quote": "Copies are kept for 35 days"}]

    result = answer_question(
        question(), CHUNKS, FakeLLM(reply(status="needs_review", citations=cites)), settings
    )

    assert result.answer.status == "needs_review"
    assert len(result.answer.citations) == 1


@pytest.mark.parametrize("content", ["not json at all", "[1, 2]", "", "{broken"])
def test_unparseable_reply_needs_review(settings: Settings, content: str) -> None:
    result = answer_question(question(), CHUNKS, FakeLLM(content), settings)

    assert result.answer.status == "needs_review"
    assert result.answer.confidence == 0.0
    assert result.raw_response == content
    assert result.usage == USAGE


def test_unknown_status_and_bad_fields_do_not_raise(settings: Settings) -> None:
    llm = FakeLLM('{"text": 5, "status": "maybe", "confidence": "high", "citations": "none"}')

    result = answer_question(question(), CHUNKS, llm, settings)

    assert result.answer.status == "needs_review"
    assert result.answer.confidence == 0.0


def test_confidence_is_clamped(settings: Settings) -> None:
    cites = [{"fragment": 2, "quote": "Restore tests are run quarterly"}]

    result = answer_question(question(), CHUNKS, FakeLLM(reply(confidence=7, citations=cites)), settings)

    assert result.answer.confidence == 1.0


def test_json_in_markdown_fence_is_parsed() -> None:
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_normalize_text_folds_case_space_and_punctuation() -> None:
    assert normalize_text("  Hello,\n  WORLD!  ") == "hello world"


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("Copies are kept for 35 days", True),
        ("copies are kept for 35 days.", True),
        ("Copies are kept for thirty five days", False),
        ("Backups of production databases are made every day at 02:00 and archived offsite", False),
        ("Backups of production databases are made every day at 2:00", True),
        ("35 days", False),
        ("", False),
    ],
)
def test_quote_in_text(quote: str, expected: bool) -> None:
    assert quote_in_text(quote, CHUNKS[0].text) is expected


def test_quote_check_handles_cyrillic_and_kazakh() -> None:
    text = "Резервные копии хранятся 35 дней. Деректерді шифрлау AES-256 арқылы жүзеге асады."
    assert quote_in_text("резервные копии хранятся 35 дней", text)
    assert quote_in_text("Деректерді шифрлау AES-256 арқылы", text)
    assert not quote_in_text("Резервные копии хранятся 90 дней и шифруются", text)


def test_format_fragments_numbers_from_one_and_shows_missing_date() -> None:
    undated = chunk(1, "Text").model_copy(update={"effective_date": None})

    rendered = format_fragments([undated])

    assert rendered.startswith("[1] Policy | section: Backups | effective: unknown | lang: en\nText")


class SequenceLLM:
    def __init__(self, *contents: str) -> None:
        self.contents = list(contents)
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str) -> LLMReply:
        self.calls.append((system, user))
        return LLMReply(content=self.contents[len(self.calls) - 1], usage=USAGE)


QUOTE = "Backups of production databases are made every day"
RU_TEXT = "Резервные копии делаются каждый день [1]."


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("How often are backups made?", "English"),
        ("Как часто делаются резервные копии?", "Russian"),
        ("Сақтық көшірмелер қаншалықты жиі жасалады?", "Kazakh"),
    ],
)
def test_user_message_names_answer_language(settings: Settings, text: str, name: str) -> None:
    llm = SequenceLLM(reply(citations=[]), reply(citations=[]))

    answer_question(question(text), CHUNKS, llm, settings)

    assert f"Answer language: {name}" in llm.calls[0][1]


def test_wrong_language_is_retried_once_and_fixed(settings: Settings) -> None:
    citations = [{"fragment": 1, "quote": QUOTE}]
    llm = SequenceLLM(reply(text=RU_TEXT, citations=citations), reply(citations=citations))

    result = answer_question(question(), CHUNKS, llm, settings)

    assert len(llm.calls) == 2
    assert "previous answer was not in English" in llm.calls[1][1]
    assert result.answer.status == "answered"
    assert result.answer.text == "Backups run daily [1]."
    assert result.usage is not None
    assert result.usage.prompt_tokens == 200
    assert result.usage.cost_usd == pytest.approx(0.002)


def test_wrong_language_after_retry_needs_review(settings: Settings) -> None:
    citations = [{"fragment": 1, "quote": QUOTE}]
    llm = SequenceLLM(reply(text=RU_TEXT, citations=citations), reply(text=RU_TEXT, citations=citations))

    result = answer_question(question(), CHUNKS, llm, settings)

    assert len(llm.calls) == 2
    assert result.answer.status == "needs_review"
    assert result.answer.text == RU_TEXT
    assert len(result.answer.citations) == 1


def test_matching_language_makes_one_call(settings: Settings) -> None:
    llm = FakeLLM(reply(text=RU_TEXT, citations=[{"fragment": 1, "quote": QUOTE}]))

    result = answer_question(question("Как часто делаются резервные копии?"), CHUNKS, llm, settings)

    assert len(llm.calls) == 1
    assert result.answer.status == "answered"


def test_no_data_in_wrong_language_is_retried(settings: Settings) -> None:
    llm = SequenceLLM(
        reply(text="В базе знаний нет данных.", status="no_data"),
        reply(text="The knowledge base has no data on this.", status="no_data"),
    )

    result = answer_question(question(), CHUNKS, llm, settings)

    assert result.answer.status == "no_data"
    assert result.answer.text == "The knowledge base has no data on this."
