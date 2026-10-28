"""Parsing of knowledge-base files (DOCX, PDF, Markdown, XLSX) into :class:`Document`."""

import hashlib
from collections.abc import Callable
from pathlib import Path

from rfp.documents.common import Parsed
from rfp.documents.docx_reader import read_docx
from rfp.documents.language import detect_language, normalize_language
from rfp.documents.markdown_reader import read_markdown
from rfp.documents.pdf_reader import read_pdf
from rfp.documents.xlsx_reader import read_xlsx
from rfp.models import Document, Section

_READERS: dict[str, Callable[[Path], Parsed]] = {
    ".docx": read_docx,
    ".pdf": read_pdf,
    ".md": read_markdown,
    ".markdown": read_markdown,
    ".xlsx": read_xlsx,
}

SUPPORTED_SUFFIXES = frozenset(_READERS)


def parse_document(path: Path, doc_id: str | None = None) -> Document:
    """Read a knowledge-base file; ``doc_id`` defaults to a slug of the file name."""
    reader = _READERS.get(path.suffix.lower())
    if reader is None:
        raise ValueError(f"Unsupported file type: {path.suffix or path.name}")
    parsed = reader(path)
    title = parsed.title or path.stem
    sections = [
        section if section.heading else Section(heading=title, text=section.text, order=section.order)
        for section in parsed.sections
    ]
    language = normalize_language(parsed.language) or detect_language(" ".join(s.text for s in sections))
    return Document(
        doc_id=doc_id or parsed.doc_id or path.stem,
        title=title,
        language=language,
        effective_date=parsed.effective_date,
        source_path=str(path),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        sections=sections,
    )
