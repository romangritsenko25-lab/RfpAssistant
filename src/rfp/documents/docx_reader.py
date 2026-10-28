from pathlib import Path

from docx import Document as open_docx
from docx.table import Table

from rfp.documents.common import Parsed, SectionCollector
from rfp.docx_blocks import heading_level, iter_blocks


def read_docx(path: Path) -> Parsed:
    """Split a DOCX into sections at Heading styles; tables become ``a | b | c`` lines."""
    doc = open_docx(str(path))
    collector = SectionCollector()
    for block in iter_blocks(doc):
        if isinstance(block, Table):
            for row in block.rows:
                collector.add(" | ".join(cell.text.strip() for cell in row.cells))
            continue
        if heading_level(block) is not None and block.text.strip():
            collector.start(block.text)
        else:
            collector.add(block.text)
    props = doc.core_properties
    stamp = props.modified or props.created
    return Parsed(
        sections=collector.finish(),
        title=props.title or None,
        doc_id=props.identifier or None,
        language=props.language or None,
        effective_date=stamp.date() if stamp else None,
    )
