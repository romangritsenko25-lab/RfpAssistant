from collections.abc import Iterator
from pathlib import Path

from docx import Document as open_docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from rfp.docx_blocks import heading_level, iter_blocks
from rfp.models import Location, Question
from rfp.questions.rules import is_number_label, is_question, question_text, split_number

_LIST_STYLE_PREFIX = "list number"

Candidate = tuple[str | None, str, Location]  # (number, text body, location)


def extract_docx_questions(path: Path) -> list[Question]:
    """Find questions and requirements in body paragraphs and table rows, in document order."""
    doc = open_docx(str(path))
    numbering = _WordNumbering()
    questions: list[Question] = []
    for block_index, block in enumerate(iter_blocks(doc)):
        if isinstance(block, Table):
            candidates = _table_candidates(block, block_index)
        else:
            candidates = _paragraph_candidates(block, block_index, numbering)
        for number, body, location in candidates:
            questions.append(
                Question(
                    qid=f"q{len(questions) + 1}", text=question_text(body), number=number, location=location
                )
            )
    return questions


def _paragraph_candidates(
    paragraph: Paragraph, block: int, numbering: "_WordNumbering"
) -> Iterator[Candidate]:
    word_number = numbering.label(paragraph)
    text = paragraph.text.strip()
    if not text or heading_level(paragraph) is not None:
        return
    manual_number, body = split_number(text)
    number = manual_number or word_number
    if is_question(body, numbered=number is not None):
        yield number, body, Location(block=block)


def _table_candidates(table: Table, block: int) -> Iterator[Candidate]:
    for row_index, row in enumerate(table.rows):
        cells = unique_cells(row)
        label = cells[0][1].text.strip() if cells else ""
        for col_index, cell in cells:
            text = cell.text.strip()
            if not text or is_number_label(text):
                continue
            manual_number, body = split_number(text)
            number = manual_number or (
                label.strip("().") if col_index > 0 and is_number_label(label) else None
            )
            if is_question(body, numbered=number is not None):
                yield number, body, Location(block=block, table_row=row_index, table_col=col_index)
                break


def unique_cells(row) -> list[tuple[int, object]]:
    """Cells of a row with merged cells reported once, keeping their column index."""
    seen: set[int] = set()
    cells = []
    for index, cell in enumerate(row.cells):
        if id(cell._tc) not in seen:
            seen.add(id(cell._tc))
            cells.append((index, cell))
    return cells


class _WordNumbering:
    """Reconstructs ``1`` / ``1.2`` labels for paragraphs that use Word's automatic numbering."""

    def __init__(self) -> None:
        self._counters: dict[str, list[int]] = {}

    def label(self, paragraph: Paragraph) -> str | None:
        key_level = _list_key_and_level(paragraph)
        if key_level is None:
            return None
        key, level = key_level
        counters = self._counters.setdefault(key, [])
        del counters[level + 1 :]
        counters.extend([0] * (level + 1 - len(counters)))
        counters[level] += 1
        return ".".join(str(n) for n in counters)


def _list_key_and_level(paragraph: Paragraph) -> tuple[str, int] | None:
    properties = paragraph._p.pPr
    num_pr = properties.numPr if properties is not None else None
    if num_pr is not None and num_pr.numId is not None:
        level = num_pr.ilvl.val if num_pr.ilvl is not None else 0
        return f"num:{num_pr.numId.val}", level
    style = paragraph.style
    if style is not None and style.name and style.name.lower().startswith(_LIST_STYLE_PREFIX):
        return f"style:{style.name}", 0
    return None
