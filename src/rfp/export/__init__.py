"""Writing answers back into the format of the input document."""

from collections.abc import Sequence
from pathlib import Path

from rfp.export.docx_export import export_docx, export_docx_report
from rfp.export.verify import ExportVerificationError, verify_docx, verify_xlsx
from rfp.export.xlsx_export import AnswerHeader, export_xlsx
from rfp.models import Answer, Question


def export_answers(
    source: Path,
    questions: list[Question],
    answers: dict[str, Answer],
    dest: Path,
    answer_headers: Sequence[AnswerHeader] = (),
) -> None:
    """Export in the input's own format; a PDF input produces a DOCX report (``dest`` should be .docx).

    ``answer_headers`` applies to XLSX only: titles of answer columns added to the file. An XLSX or
    DOCX result is reopened and compared with the source; ``ExportVerificationError`` means the file
    must not be handed out.
    """
    suffix = source.suffix.lower()
    if suffix == ".xlsx":
        export_xlsx(source, questions, answers, dest, answer_headers)
        verify_xlsx(source, dest, questions, answers, answer_headers)
    elif suffix == ".docx":
        export_docx(source, questions, answers, dest)
        verify_docx(source, dest, questions, answers)
    elif suffix == ".pdf":
        export_docx_report(questions, answers, dest)
    else:
        raise ValueError(f"Unsupported input type: {suffix}")


__all__ = [
    "AnswerHeader",
    "ExportVerificationError",
    "export_answers",
    "export_docx",
    "export_docx_report",
    "export_xlsx",
    "verify_docx",
    "verify_xlsx",
]
