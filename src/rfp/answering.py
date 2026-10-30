"""Answer generation from retrieved fragments, with code-level verification of every citation."""

import json
import re
import unicodedata
from difflib import SequenceMatcher

from pydantic import BaseModel

from rfp.config import Settings
from rfp.documents.language import detect_language
from rfp.llm import ChatClient, LLMUsage
from rfp.models import Answer, AnswerStatus, Citation, Question, RetrievedChunk, ShortAnswer

# A quote that is not a verbatim substring still counts when at least this share of its characters
# is found, in order, inside the fragment as runs of MIN_RUN+ characters. This tolerates a dropped
# word, a changed punctuation mark or a number format, but not a rewritten or invented sentence.
FUZZY_THRESHOLD = 0.9
MIN_RUN = 5
MIN_QUOTE_CHARS = 8

NO_DATA_TEXT = {
    "ru": "В базе знаний нет данных для ответа на этот вопрос.",
    "kk": "Бұл сұраққа жауап беруге арналған деректер білім базасында жоқ.",
    "en": "The knowledge base has no data to answer this question.",
}
UNPARSED_TEXT = {
    "ru": "Ответ модели не удалось разобрать, требуется ручная проверка.",
    "kk": "Модель жауабын талдау мүмкін болмады, қолмен тексеру қажет.",
    "en": "The model response could not be parsed; manual review is required.",
}

_SHORT: tuple[ShortAnswer, ...] = ("yes", "no", "partial", "n/a")
_STATUSES: tuple[AnswerStatus, ...] = ("answered", "no_data", "needs_review")
_NON_WORD_RE = re.compile(r"[\W_]+")
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class GeneratedAnswer(BaseModel):
    """An answer plus the data the request log needs: model usage, rejected citations, raw reply."""

    answer: Answer
    usage: LLMUsage | None = None
    rejected_citations: int = 0
    raw_response: str = ""


def normalize_text(text: str) -> str:
    """Lowercase, fold Unicode forms, and reduce punctuation and whitespace runs to single spaces."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _NON_WORD_RE.sub(" ", folded).strip()


def quote_in_text(quote: str, text: str) -> bool:
    """True when ``quote`` is in ``text`` after normalisation, or matches it closely enough.

    Exact (normalised) containment passes. Otherwise the quote must be at least ``MIN_QUOTE_CHARS``
    long and ``FUZZY_THRESHOLD`` of its characters must lie in common runs of ``MIN_RUN``+ characters.
    """
    needle = normalize_text(quote)
    haystack = normalize_text(text)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    if needle in haystack:
        return True
    matcher = SequenceMatcher(None, needle, haystack, autojunk=False)
    matched = sum(block.size for block in matcher.get_matching_blocks() if block.size >= MIN_RUN)
    return matched / len(needle) >= FUZZY_THRESHOLD


def format_fragments(chunks: list[RetrievedChunk]) -> str:
    """Render fragments as a numbered list (from 1) with the metadata the prompt refers to."""
    parts = []
    for number, chunk in enumerate(chunks, start=1):
        date = chunk.effective_date.isoformat() if chunk.effective_date else "unknown"
        header = (
            f"[{number}] {chunk.title} | section: {chunk.heading} | "
            f"effective: {date} | lang: {chunk.language}"
        )
        parts.append(f"{header}\n{chunk.text}")
    return "\n\n".join(parts)


def build_user_message(question: str, chunks: list[RetrievedChunk]) -> str:
    return f"Question:\n{question}\n\nFragments:\n\n{format_fragments(chunks)}"


def parse_model_json(raw: str) -> dict | None:
    """Decode the model reply as a JSON object, tolerating a markdown fence; None when it is not one."""
    text = _FENCE_RE.sub("", raw.strip())
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def verify_citations(raw_citations: object, chunks: list[RetrievedChunk]) -> tuple[list[Citation], int]:
    """Keep citations that point at a given fragment and quote its text; return them and the reject count."""
    if not isinstance(raw_citations, list):
        return [], 0
    verified: list[Citation] = []
    seen: set[tuple[int, str]] = set()
    rejected = 0
    for item in raw_citations:
        chunk = _cited_chunk(item, chunks)
        quote = item.get("quote") if isinstance(item, dict) else None
        if chunk is None or not isinstance(quote, str) or not quote_in_text(quote, chunk.text):
            rejected += 1
            continue
        key = (chunk.chunk_id, normalize_text(quote))
        if key in seen:
            continue
        seen.add(key)
        verified.append(
            Citation(
                doc_id=chunk.doc_id, section=chunk.heading, snippet=quote.strip(), chunk_id=chunk.chunk_id
            )
        )
    return verified, rejected


def _cited_chunk(item: object, chunks: list[RetrievedChunk]) -> RetrievedChunk | None:
    if not isinstance(item, dict):
        return None
    number = item.get("fragment")
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= len(chunks):
        return None
    return chunks[number - 1]


def answer_question(
    question: Question, chunks: list[RetrievedChunk], llm: ChatClient, settings: Settings
) -> GeneratedAnswer:
    """Draft an answer from ``chunks`` only; every returned citation is checked against the fragments.

    Without fragments the model is not called and the status is ``no_data``. An unparseable reply,
    an ``answered`` result with no verified citation, or confidence below the configured threshold
    all give ``needs_review``.
    """
    language = detect_language(question.text)
    if not chunks:
        return GeneratedAnswer(
            answer=Answer(
                qid=question.qid, text=_message(NO_DATA_TEXT, language), status="no_data", confidence=1.0
            )
        )

    system = settings.answer_prompt_path.read_text(encoding="utf-8")
    reply = llm.complete_json(system, build_user_message(question.text, chunks))
    data = parse_model_json(reply.content)
    if data is None:
        answer = Answer(
            qid=question.qid, text=_message(UNPARSED_TEXT, language), status="needs_review", confidence=0.0
        )
        return GeneratedAnswer(answer=answer, usage=reply.usage, raw_response=reply.content)

    status = data.get("status") if data.get("status") in _STATUSES else "needs_review"
    confidence = _confidence(data.get("confidence"))
    text = data.get("text") if isinstance(data.get("text"), str) else ""
    citations, rejected = verify_citations(data.get("citations"), chunks)

    if status == "no_data":
        citations = []
        text = text.strip() or _message(NO_DATA_TEXT, language)
    elif status == "answered" and (not citations or confidence < settings.confidence_threshold):
        status = "needs_review"
    if not text.strip():
        status, text = "needs_review", _message(UNPARSED_TEXT, language)

    answer = Answer(
        qid=question.qid,
        text=text.strip(),
        status=status,
        confidence=confidence,
        citations=citations,
        short=_short(data.get("short")) if status == "answered" else None,
    )
    return GeneratedAnswer(
        answer=answer, usage=reply.usage, rejected_citations=rejected, raw_response=reply.content
    )


def _short(value: object) -> ShortAnswer | None:
    """The model's short rating when it is one of the four known values, else None."""
    cleaned = value.strip().casefold() if isinstance(value, str) else ""
    return next((v for v in _SHORT if v == cleaned), None)


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0.0
    return min(1.0, max(0.0, float(value)))


def _message(table: dict[str, str], language: str) -> str:
    return table.get(language, table["en"])
