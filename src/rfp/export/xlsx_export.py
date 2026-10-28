from copy import copy
from pathlib import Path
from typing import NamedTuple

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string

from rfp.export.formatting import answer_with_sources
from rfp.models import Answer, Question


class AnswerHeader(NamedTuple):
    """Title for an answer column the source file did not have; styled like the cell to its left."""

    sheet: str
    row: int
    col: str
    text: str


def export_xlsx(
    source: Path,
    questions: list[Question],
    answers: dict[str, Answer],
    dest: Path,
    answer_header: AnswerHeader | None = None,
) -> None:
    """Write each answer into its answer cell of a copy of ``source``; nothing else is touched.

    Refuses (``ValueError``) to write into the question column or over a cell that already holds
    the question text, so a wrong column choice cannot destroy the questions.
    """
    workbook = load_workbook(source)
    for question in questions:
        answer = answers.get(question.qid)
        if answer is None:
            continue
        location = question.location
        if location.sheet is None or location.row is None or location.answer_col is None:
            raise ValueError(f"Question {question.qid} has no XLSX location")
        if location.answer_col.upper() == (location.question_col or "").upper():
            raise ValueError(f"Question {question.qid}: the answer column is the question column")
        cell = workbook[location.sheet][f"{location.answer_col}{location.row}"]
        if isinstance(cell.value, str) and cell.value.strip() == question.text:
            raise ValueError(
                f"Cell {location.answer_col}{location.row} already holds the question text; "
                "it would be overwritten. Check the answer column."
            )
        cell.value = answer_with_sources(answer)
    if answer_header is not None:
        _write_header(workbook, answer_header)
    workbook.save(dest)


def _write_header(workbook, header: AnswerHeader) -> None:
    sheet = workbook[header.sheet]
    cell = sheet[f"{header.col}{header.row}"]
    if cell.value is not None:
        return
    cell.value = header.text
    index = column_index_from_string(header.col)
    if index > 1:
        cell._style = copy(sheet.cell(row=header.row, column=index - 1)._style)
