"""Helpers for walking the body of a DOCX in document order."""

import re
from collections.abc import Iterator

from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

Block = Paragraph | Table

_HEADING_STYLE_RE = re.compile(r"^(?:heading|заголовок)\s*(\d+)$", re.IGNORECASE)


def iter_blocks(doc: DocxDocument) -> Iterator[Block]:
    """Yield body paragraphs and tables in the order they appear."""
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def heading_level(paragraph: Paragraph) -> int | None:
    """Return the heading level (1..9) of a paragraph, or None for body text."""
    style = paragraph.style
    match = _HEADING_STYLE_RE.match(style.name) if style is not None and style.name else None
    return int(match.group(1)) if match else None
