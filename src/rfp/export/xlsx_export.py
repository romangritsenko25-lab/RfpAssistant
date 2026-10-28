from pathlib import Path

from openpyxl import load_workbook

from rfp.export.formatting import answer_with_sources
from rfp.models import Answer, Question


def export_xlsx(source: Path, questions: list[Question], answers: dict[str, Answer], dest: Path) -> None:
    """Write each answer into its answer cell of a copy of ``source``; nothing else is touched."""
    workbook = load_workbook(source)
    for question in questions:
        answer = answers.get(question.qid)
        if answer is None:
            continue
        location = question.location
        if location.sheet is None or location.row is None or location.answer_col is None:
            raise ValueError(f"Question {question.qid} has no XLSX location")
        workbook[location.sheet][f"{location.answer_col}{location.row}"] = answer_with_sources(answer)
    workbook.save(dest)
