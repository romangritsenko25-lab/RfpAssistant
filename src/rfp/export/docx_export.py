from pathlib import Path

from docx import Document as open_docx
from docx.document import Document as DocxDocument
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

from rfp.docx_blocks import iter_blocks
from rfp.export.formatting import sources_line
from rfp.models import Answer, Question

ANSWER_STYLE = "RFP Answer"
_SOURCES_COLOR = RGBColor(0x59, 0x59, 0x59)
_SOURCES_SIZE = Pt(8)


def export_docx(source: Path, questions: list[Question], answers: dict[str, Answer], dest: Path) -> None:
    """Insert each answer as a new paragraph right under its question in a copy of ``source``."""
    doc = open_docx(str(source))
    _ensure_answer_style(doc)
    blocks = list(iter_blocks(doc))  # resolved up front: insertions shift later positions
    for question in questions:
        answer = answers.get(question.qid)
        if answer is not None:
            _write_answer(_new_paragraph(doc, blocks, question), answer)
    doc.save(dest)


def export_docx_report(questions: list[Question], answers: dict[str, Answer], dest: Path) -> None:
    """Build a standalone DOCX of question, answer and sources; used for PDF inputs."""
    doc = open_docx()
    _ensure_answer_style(doc)
    doc.add_heading("Answers", level=1)
    for question in questions:
        answer = answers.get(question.qid)
        if answer is None:
            continue
        label = f"{question.number}. " if question.number else ""
        doc.add_paragraph().add_run(f"{label}{question.text}").bold = True
        _write_answer(doc.add_paragraph(), answer)
    doc.save(dest)


def _new_paragraph(doc: DocxDocument, blocks: list, question: Question) -> Paragraph:
    location = question.location
    if location.block is None:
        raise ValueError(f"Question {question.qid} has no DOCX location")
    block = blocks[location.block]
    if isinstance(block, Table):
        return block.cell(location.table_row or 0, location.table_col or 0).add_paragraph()
    new_p = OxmlElement("w:p")
    block._p.addnext(new_p)
    return Paragraph(new_p, doc)


def _write_answer(paragraph: Paragraph, answer: Answer) -> None:
    paragraph.style = ANSWER_STYLE
    paragraph.add_run(answer.text)
    sources = sources_line(answer)
    if sources:
        run = paragraph.add_run()
        run.add_break()
        run.add_text(sources)
        run.font.size = _SOURCES_SIZE
        run.font.color.rgb = _SOURCES_COLOR


def _ensure_answer_style(doc: DocxDocument) -> None:
    if ANSWER_STYLE in doc.styles:
        return
    style = doc.styles.add_style(ANSWER_STYLE, WD_STYLE_TYPE.PARAGRAPH)
    style.base_style = doc.styles["Normal"]
    style.paragraph_format.left_indent = Cm(0.8)
    style.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
