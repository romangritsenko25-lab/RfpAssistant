"""DOCX layout map: a text picture of the document for the model, and code that checks its reply.

The model names, by block index, which paragraphs or table cells are questions and where each answer
goes. The question texts are always read from the document, never taken from the model's reply.
"""

from typing import Literal

from docx import Document as open_docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from pydantic import BaseModel, Field

from rfp.docx_blocks import heading_level, iter_blocks
from rfp.models import Location, Question
from rfp.questions.docx_questions import unique_cells
from rfp.questions.layout_validate import LayoutRejected
from rfp.questions.placeholders import is_placeholder
from rfp.questions.rules import is_number_label, question_text, split_number

MAX_PARAGRAPH_CHARS = 200
MAX_CELL_CHARS = 100
WINDOW_CHARS = 24000


class DocxPlace(BaseModel):
    place: Literal["paragraph_below", "cell"] = "paragraph_below"
    table_row: int | None = Field(default=None, ge=0)
    table_col: int | None = Field(default=None, ge=0)


class DocxItem(BaseModel):
    block: int = Field(ge=0)
    table_row: int | None = Field(default=None, ge=0)
    table_col: int | None = Field(default=None, ge=0)
    number: str | None = None
    answer: DocxPlace = Field(default_factory=DocxPlace)


class DocxReply(BaseModel):
    questions: list[DocxItem]


def render_windows(path) -> list[str]:
    """The document as numbered blocks, cut into pieces small enough for one model call each."""
    doc = open_docx(str(path))
    windows: list[str] = []
    current: list[str] = []
    size = 0
    for index, block in enumerate(iter_blocks(doc)):
        text = _render_block(index, block)
        if not text:
            continue
        if current and size + len(text) > WINDOW_CHARS:
            windows.append("\n".join(current))
            current, size = [], 0
        current.append(text)
        size += len(text)
    if current:
        windows.append("\n".join(current))
    return windows


def _render_block(index: int, block: Paragraph | Table) -> str:
    if isinstance(block, Table):
        rows = []
        for row_index, row in enumerate(block.rows):
            cells = [f'c{col}="{_clip(cell.text, MAX_CELL_CHARS)}"' for col, cell in unique_cells(row)]
            rows.append(f"    r{row_index}: " + " | ".join(cells))
        return f"[{index}] TABLE {len(block.rows)} rows\n" + "\n".join(rows)
    text = block.text.strip()
    if not text:
        return ""
    style = block.style.name if block.style is not None and block.style.name else ""
    tag = f"P, {style}" if heading_level(block) is not None else "P"
    return f"[{index}] {tag}: {_clip(text, MAX_PARAGRAPH_CHARS)}"


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_questions(path, items: list[DocxItem]) -> tuple[list[Question], int, int]:
    """Verify the model's items against the document; return the questions and how many answers go
    to a table cell and to a new paragraph. Raises ``LayoutRejected`` on the first group of problems."""
    doc = open_docx(str(path))
    blocks = list(iter_blocks(doc))
    problems: list[str] = []
    found: dict[tuple[int, int, int], Question] = {}
    used_cells: set[tuple[int, int, int]] = set()
    for item in sorted(items, key=lambda i: (i.block, i.table_row or 0, i.table_col or 0)):
        key = (item.block, item.table_row or 0, item.table_col or 0)
        if key in found:
            continue
        try:
            question = _question(blocks, item, used_cells)
        except LayoutRejected as exc:
            problems.append(str(exc))
            continue
        found[key] = question
    if problems:
        raise LayoutRejected("; ".join(problems[:5]))
    if not found:
        raise LayoutRejected("the model found no questions in the document")
    questions = [q.model_copy(update={"qid": f"q{n}"}) for n, q in enumerate(found.values(), 1)]
    cells = sum(1 for q in questions if q.location.answer_table_row is not None)
    return questions, len(questions) - cells, cells


def _question(blocks: list, item: DocxItem, used_cells: set[tuple[int, int, int]]) -> Question:
    if item.block >= len(blocks):
        raise LayoutRejected(f"block {item.block} does not exist")
    block = blocks[item.block]
    if isinstance(block, Table):
        return _table_question(block, item, used_cells)
    if item.table_row is not None or item.answer.place == "cell":
        raise LayoutRejected(f"block {item.block} is a paragraph, not a table")
    text = block.text.strip()
    if not text:
        raise LayoutRejected(f"block {item.block} has no text")
    manual_number, body = split_number(text)
    return Question(
        qid="",
        text=question_text(body),
        number=item.number or manual_number,
        location=Location(block=item.block),
    )


def _table_question(table: Table, item: DocxItem, used_cells: set[tuple[int, int, int]]) -> Question:
    where = f"table block {item.block}"
    if item.table_row is None or item.table_col is None:
        raise LayoutRejected(f"{where}: the question cell is not given")
    cell = _cell(table, item.table_row, item.table_col)
    if cell is None:
        raise LayoutRejected(f"{where}: cell r{item.table_row} c{item.table_col} does not exist")
    text = cell.text.strip()
    if not text:
        raise LayoutRejected(f"{where}: cell r{item.table_row} c{item.table_col} has no text")
    answer_row = answer_col = None
    if item.answer.place == "cell":
        answer_row, answer_col = item.answer.table_row, item.answer.table_col
        target = (
            _cell(table, answer_row, answer_col)
            if answer_row is not None and answer_col is not None
            else None
        )
        if target is None:
            raise LayoutRejected(f"{where}: the answer cell does not exist")
        if target._tc is cell._tc:
            raise LayoutRejected(f"{where}: the answer cell is the question cell")
        if not is_placeholder(target.text):
            raise LayoutRejected(f"{where}: the answer cell r{answer_row} c{answer_col} is not empty")
        slot = (item.block, answer_row, answer_col)
        if slot in used_cells:
            raise LayoutRejected(f"{where}: two answers go to cell r{answer_row} c{answer_col}")
        used_cells.add(slot)
    manual_number, body = split_number(text)
    first = unique_cells(table.rows[item.table_row])[0]
    label = first[1].text.strip()
    number = (
        item.number
        or manual_number
        or (label.strip("().") if item.table_col > 0 and is_number_label(label) else None)
    )
    return Question(
        qid="",
        text=question_text(body),
        number=number,
        location=Location(
            block=item.block,
            table_row=item.table_row,
            table_col=item.table_col,
            answer_table_row=answer_row,
            answer_table_col=answer_col,
        ),
    )


def _cell(table: Table, row: int, col: int):
    try:
        return table.cell(row, col)
    except IndexError:
        return None
