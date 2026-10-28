from pathlib import Path

from pypdf import PdfReader

from rfp.models import Location, Question
from rfp.questions.rules import is_question, question_text, split_number

_TERMINAL_PUNCTUATION = (".", "?", "!", ":", ";")


def extract_pdf_questions(path: Path) -> list[Question]:
    """Find questions and requirements in the text layer, in reading order."""
    questions: list[Question] = []
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        for line_number, text in _join_wrapped_items((page.extract_text() or "").splitlines()):
            number, body = split_number(text)
            if is_question(body, numbered=number is not None):
                questions.append(
                    Question(
                        qid=f"q{len(questions) + 1}",
                        text=question_text(body),
                        number=number,
                        location=Location(page=page_number, line=line_number),
                    )
                )
    return questions


def _join_wrapped_items(lines: list[str]) -> list[tuple[int, str]]:
    """Merge the continuation lines of a numbered item; returns (first line number, text) pairs."""
    items: list[tuple[int, str]] = []
    open_item = False
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            open_item = False
            continue
        starts_item = split_number(line)[0] is not None
        if open_item and not starts_item:
            first_line, text = items[-1]
            items[-1] = (first_line, f"{text} {line}")
        else:
            items.append((line_number, line))
        open_item = (starts_item or open_item) and not line.endswith(_TERMINAL_PUNCTUATION)
    return items
