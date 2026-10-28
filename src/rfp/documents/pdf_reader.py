import re
from collections import Counter
from itertools import groupby
from pathlib import Path
from typing import NamedTuple

from pypdf import PdfReader

from rfp.documents.common import Parsed, SectionCollector, parse_iso_date
from rfp.models import Section

_MAX_HEADING_LEN = 80
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+\S")
_SENTENCE_PUNCTUATION = (".", ",", ";", ":", "?", "!")
_SIZE_MARGIN = 0.5


class Line(NamedTuple):
    text: str
    size: float


def read_pdf(path: Path) -> Parsed:
    """Extract text per page; sections follow headings, otherwise there is one section per page.

    Identity comes from the custom document-info keys ``/DocId``, ``/Language`` and
    ``/EffectiveDate``. The PDF creation date is never used: generators fill it with a placeholder.
    """
    reader = PdfReader(str(path))
    pages = [_page_lines(page) for page in reader.pages]
    info = reader.metadata or {}
    sections = _sections_by_size(pages) or _sections_by_text_heuristic(pages) or _sections_by_page(pages)
    return Parsed(
        sections=sections,
        title=info.get("/Title") or None,
        doc_id=info.get("/DocId") or None,
        language=info.get("/Language") or None,
        effective_date=parse_iso_date(info.get("/EffectiveDate")) if info.get("/EffectiveDate") else None,
    )


def _page_lines(page) -> list[Line]:
    """Text chunks of a page with their font size; every chunk is one rendered line."""
    lines: list[Line] = []

    def visit(text: str, _cm: list[float], _tm: list[float], _font: dict | None, size: float) -> None:
        if text.strip():
            lines.append(Line(text.strip(), round(size, 1)))

    page.extract_text(visitor_text=visit)
    return lines


def is_heading_line(line: str) -> bool:
    """Heuristic: a short line without sentence punctuation that is numbered or ALL CAPS."""
    text = line.strip()
    if not text or len(text) > _MAX_HEADING_LEN or text.endswith(_SENTENCE_PUNCTUATION):
        return False
    if _NUMBERED_HEADING_RE.match(text):
        return True
    return text.isupper() and sum(ch.isalpha() for ch in text) >= 3


def _sections_by_size(pages: list[list[Line]]) -> list[Section]:
    """Lines set in a font larger than the body text are headings; wrapped headings are joined."""
    lines = [line for page in pages for line in page]
    weights = Counter[float]()
    for line in lines:
        weights[line.size] += len(line.text)
    if not weights:
        return []
    body_size = weights.most_common(1)[0][0]
    heading_sizes = {size for size in weights if size > body_size + _SIZE_MARGIN}
    if not heading_sizes:
        return []
    collector = SectionCollector()
    for (is_heading, _), group in groupby(lines, key=lambda line: (line.size in heading_sizes, line.size)):
        parts = [line.text for line in group]
        if is_heading:
            collector.start(" ".join(parts))
        else:
            for part in parts:
                collector.add(part)
    return collector.finish()


def _sections_by_text_heuristic(pages: list[list[Line]]) -> list[Section]:
    collector = SectionCollector()
    found = False
    for lines in pages:
        for line in lines:
            heading = is_heading_line(line.text)
            found = found or heading
            if heading:
                collector.start(line.text)
            else:
                collector.add(line.text)
    return collector.finish() if found else []


def _sections_by_page(pages: list[list[Line]]) -> list[Section]:
    collector = SectionCollector()
    for number, lines in enumerate(pages, start=1):
        collector.start(f"Page {number}")
        for line in lines:
            collector.add(line.text)
    return collector.finish()
