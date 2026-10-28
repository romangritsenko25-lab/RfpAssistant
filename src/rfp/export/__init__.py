"""Writing answers back into the format of the input document."""

from pathlib import Path

from rfp.export.docx_export import export_docx, export_docx_report
from rfp.export.xlsx_export import export_xlsx
from rfp.models import Answer, Question


def export_answers(source: Path, questions: list[Question], answers: dict[str, Answer], dest: Path) -> None:
    """Export in the input's own format; a PDF input produces a DOCX report (``dest`` should be .docx)."""
    suffix = source.suffix.lower()
    if suffix == ".xlsx":
        export_xlsx(source, questions, answers, dest)
    elif suffix == ".docx":
        export_docx(source, questions, answers, dest)
    elif suffix == ".pdf":
        export_docx_report(questions, answers, dest)
    else:
        raise ValueError(f"Unsupported input type: {suffix}")


__all__ = ["export_answers", "export_docx", "export_docx_report", "export_xlsx"]
