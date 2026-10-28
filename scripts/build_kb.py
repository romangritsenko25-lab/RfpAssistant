"""Render the Markdown sources of the synthetic knowledge base into their target formats.

Every file in ``data/kb_src`` has a flat YAML header (title, section, language, effective_date,
format, doc_id) and a Markdown body. The ``format`` field decides what is written to
``data/kb``: DOCX, PDF (with a text layer), XLSX or a plain copy of the Markdown file.

The output is deterministic: timestamps inside the files are fixed to the effective date and
ZIP containers are re-packed with constant entry times, so a repeated run gives identical bytes.

Usage:
    uv run python scripts/build_kb.py [--src DIR] [--out DIR] [--font TTF]
"""

import argparse
import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfdoc import PDFDate, PDFDictionary, PDFInfo, PDFName, PDFString
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONT = Path(r"C:\Windows\Fonts\arial.ttf")
REQUIRED_FIELDS = ("title", "section", "language", "effective_date", "format", "doc_id")
FORMATS = ("docx", "pdf", "xlsx", "md")
LANGUAGES = ("ru", "kk", "en")
AUTHOR = "Steppelight Technologies (fictional company)"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
TABLE_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


@dataclass
class Block:
    """One structural element of a document body."""

    kind: str  # h1 | h2 | p | ul | ol | table
    text: str = ""
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Doc:
    meta: dict[str, str]
    blocks: list[Block]
    source: Path

    @property
    def stamp(self) -> dt.datetime:
        return dt.datetime.fromisoformat(self.meta["effective_date"])

    @property
    def keywords(self) -> str:
        return f"{self.meta['doc_id']}; {self.meta['section']}; {self.meta['language']}"


def parse_source(path: Path) -> Doc:
    raw = path.read_text(encoding="utf-8")
    match = FRONT_MATTER.match(raw)
    if not match:
        raise ValueError(f"{path.name}: missing YAML header")
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"{path.name}: bad header line {line!r}")
        meta[key.strip()] = value.strip().strip("\"'")
    missing = [name for name in REQUIRED_FIELDS if not meta.get(name)]
    if missing:
        raise ValueError(f"{path.name}: header lacks {missing}")
    if meta["format"] not in FORMATS or meta["language"] not in LANGUAGES:
        raise ValueError(f"{path.name}: unknown format or language")
    dt.date.fromisoformat(meta["effective_date"])
    return Doc(meta=meta, blocks=parse_body(raw[match.end() :]), source=path)


def parse_body(body: str) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block("p", text=" ".join(paragraph)))
            paragraph.clear()

    for line in (ln.rstrip() for ln in body.splitlines()):
        if not line.strip():
            flush()
        elif line.startswith("## "):
            flush()
            blocks.append(Block("h2", text=line[3:].strip()))
        elif line.startswith("# "):
            flush()
            blocks.append(Block("h1", text=line[2:].strip()))
        elif line.startswith("- "):
            flush()
            _append_item(blocks, "ul", line[2:].strip())
        elif re.match(r"^\d+\. ", line):
            flush()
            _append_item(blocks, "ol", line.split(". ", 1)[1].strip())
        elif line.startswith("|"):
            flush()
            if TABLE_SEPARATOR.match(line):
                continue
            row = [cell.strip() for cell in line.strip("|").split("|")]
            if blocks and blocks[-1].kind == "table":
                blocks[-1].rows.append(row)
            else:
                blocks.append(Block("table", rows=[row]))
        else:
            paragraph.append(line.strip())
    flush()
    return blocks


def _append_item(blocks: list[Block], kind: str, text: str) -> None:
    if blocks and blocks[-1].kind == kind:
        blocks[-1].items.append(text)
    else:
        blocks.append(Block(kind, items=[text]))


def normalize_zip(data: bytes, stamp: dt.datetime) -> bytes:
    """Re-pack an OOXML container with constant entry times and a fixed modification date."""
    modified = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                content = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>" + modified.encode() + rb"\g<2>",
                    content,
                )
            entry = zipfile.ZipInfo(info.filename, date_time=ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            dst.writestr(entry, content)
    return out.getvalue()


def render_docx(doc: Doc) -> bytes:
    document = Document()
    document.styles["Normal"].font.name = "Calibri"
    document.styles["Normal"].font.size = Pt(11)
    for block in doc.blocks:
        if block.kind == "h1":
            document.add_heading(block.text, level=1)
        elif block.kind == "h2":
            document.add_heading(block.text, level=2)
        elif block.kind == "p":
            document.add_paragraph(block.text)
        elif block.kind in ("ul", "ol"):
            style = "List Bullet" if block.kind == "ul" else "List Number"
            for item in block.items:
                document.add_paragraph(item, style=style)
        elif block.kind == "table":
            table = document.add_table(rows=len(block.rows), cols=len(block.rows[0]))
            table.style = "Table Grid"
            for r, row in enumerate(block.rows):
                for c, value in enumerate(row):
                    cell = table.cell(r, c)
                    cell.text = value
                    if r == 0:
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
    props = document.core_properties
    props.title = doc.meta["title"]
    props.subject = doc.meta["section"]
    props.author = AUTHOR
    props.last_modified_by = AUTHOR
    props.language = doc.meta["language"]
    props.identifier = doc.meta["doc_id"]
    props.keywords = doc.keywords
    props.comments = f"Effective date: {doc.meta['effective_date']}. Synthetic demo data."
    props.created = doc.stamp
    props.modified = doc.stamp
    props.revision = 1
    buffer = io.BytesIO()
    document.save(buffer)
    return normalize_zip(buffer.getvalue(), doc.stamp)


def render_xlsx(doc: Doc) -> bytes:
    """One sheet per section: a table becomes header + rows, any other text becomes rows of column A."""
    sections: list[tuple[str, list[Block]]] = []
    for block in doc.blocks:
        if block.kind == "h2":
            sections.append((block.text, []))
        elif block.kind != "h1" and sections:
            sections[-1][1].append(block)
    workbook = Workbook()
    workbook.remove(workbook.active)
    used: set[str] = set()
    for heading, content in sections:
        sheet = workbook.create_sheet(_sheet_name(heading, used))
        for block in content:
            _write_block(sheet, block)
        for column in sheet.columns:
            width = max(len(str(cell.value or "")) for cell in column)
            sheet.column_dimensions[column[0].column_letter].width = min(max(width + 2, 12), 60)
    props = workbook.properties
    props.title = doc.meta["title"]
    props.subject = doc.meta["section"]
    props.creator = AUTHOR
    props.lastModifiedBy = AUTHOR
    props.identifier = doc.meta["doc_id"]
    props.language = doc.meta["language"]
    props.keywords = doc.keywords
    props.description = f"Effective date: {doc.meta['effective_date']}. Synthetic demo data."
    props.created = doc.stamp
    props.modified = doc.stamp
    buffer = io.BytesIO()
    workbook.save(buffer)
    return normalize_zip(buffer.getvalue(), doc.stamp)


def _sheet_name(heading: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", " ", heading).strip()[:31] or "Sheet"
    name, n = base, 2
    while name in used:
        suffix = f" {n}"
        name, n = base[: 31 - len(suffix)] + suffix, n + 1
    used.add(name)
    return name


def _write_block(sheet, block: Block) -> None:
    """Append a block below the existing content, separated by one blank row."""
    wrap = Alignment(wrap_text=True, vertical="top")
    row_no = 1 if sheet["A1"].value is None else sheet.max_row + 2
    if block.kind == "table":
        rows = block.rows
    elif block.kind in ("ul", "ol"):
        rows = [[item] for item in block.items]
    else:
        rows = [[block.text]]
    for offset, row in enumerate(rows):
        for col, value in enumerate(row, start=1):
            cell = sheet.cell(row=row_no + offset, column=col, value=value)
            cell.alignment = wrap
            if block.kind == "table" and offset == 0:
                cell.font = Font(bold=True)


def register_fonts(font_path: Path) -> tuple[str, str]:
    if not font_path.is_file():
        raise FileNotFoundError(f"font not found: {font_path} (use --font)")
    bold_path = font_path.with_name(font_path.stem + "bd" + font_path.suffix)
    pdfmetrics.registerFont(TTFont("KB", str(font_path)))
    pdfmetrics.registerFont(TTFont("KB-Bold", str(bold_path if bold_path.is_file() else font_path)))
    return "KB", "KB-Bold"


class _ExtraInfo(PDFInfo):
    """PDF document info that also carries custom keys (/DocId, /Section, /Language, /EffectiveDate)."""

    extra: dict[str, str] = {}  # noqa: RUF012 - replaced per instance by metadata_canvas

    def format(self, document):
        entries = {
            "Title": PDFString(self.title),
            "Author": PDFString(self.author),
            "ModDate": PDFDate(ts=document._timeStamp),
            "CreationDate": PDFDate(ts=document._timeStamp),
            "Producer": PDFString(self.producer),
            "Creator": PDFString(self.creator),
            "Subject": PDFString(self.subject),
            "Keywords": PDFString(self.keywords),
            "Trapped": PDFName(self.trapped),
        }
        entries.update({key: PDFString(value) for key, value in self.extra.items()})
        return PDFDictionary(entries).format(document)


def metadata_canvas(doc: Doc) -> type[Canvas]:
    """Canvas class whose document info gets the custom keys described above."""
    extra = {
        "DocId": doc.meta["doc_id"],
        "Section": doc.meta["section"],
        "Language": doc.meta["language"],
        "EffectiveDate": doc.meta["effective_date"],
    }

    class MetadataCanvas(Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._doc.info.__class__ = _ExtraInfo
            self._doc.info.extra = extra

    return MetadataCanvas


def render_pdf(doc: Doc) -> bytes:
    body = ParagraphStyle("body", fontName="KB", fontSize=10.5, leading=14.5, spaceAfter=6)
    h1 = ParagraphStyle("h1", parent=body, fontName="KB-Bold", fontSize=17, leading=21, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=body, fontName="KB-Bold", fontSize=13, leading=17, spaceBefore=8)
    cell_style = ParagraphStyle("cell", parent=body, fontSize=9, leading=11.5, spaceAfter=0)
    head_style = ParagraphStyle("head", parent=cell_style, fontName="KB-Bold")
    buffer = io.BytesIO()
    template = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=doc.meta["title"],
        author=AUTHOR,
        subject=doc.meta["section"],
        keywords=doc.keywords,
        creator="build_kb.py",
        invariant=1,
    )
    width = A4[0] - 40 * mm
    story: list = []
    for block in doc.blocks:
        if block.kind == "h1":
            story.append(Paragraph(escape(block.text), h1))
        elif block.kind == "h2":
            story.append(Paragraph(escape(block.text), h2))
        elif block.kind == "p":
            story.append(Paragraph(escape(block.text), body))
        elif block.kind in ("ul", "ol"):
            items = [ListItem(Paragraph(escape(item), body)) for item in block.items]
            kind = {"bulletType": "bullet"} if block.kind == "ul" else {"bulletType": "1"}
            story.append(ListFlowable(items, leftIndent=14, bulletFontName="KB", **kind))
        elif block.kind == "table":
            data = [
                [Paragraph(escape(value), head_style if r == 0 else cell_style) for value in row]
                for r, row in enumerate(block.rows)
            ]
            table = Table(data, colWidths=[width / len(block.rows[0])] * len(block.rows[0]), repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EDF2")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story += [table, Spacer(1, 8)]
    template.build(story, canvasmaker=metadata_canvas(doc))
    return buffer.getvalue()


def render(doc: Doc) -> bytes:
    match doc.meta["format"]:
        case "docx":
            return render_docx(doc)
        case "xlsx":
            return render_xlsx(doc)
        case "pdf":
            return render_pdf(doc)
        case _:
            return doc.source.read_bytes()


def build(src: Path, out: Path) -> list[dict[str, object]]:
    docs = [parse_source(path) for path in sorted(src.glob("*.md"))]
    ids = [d.meta["doc_id"] for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate doc_id in sources")
    out.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, object]] = []
    for doc in sorted(docs, key=lambda d: d.meta["doc_id"]):
        name = f"{doc.meta['doc_id']}.{doc.meta['format']}"
        data = render(doc)
        (out / name).write_bytes(data)
        entries.append(
            {
                "doc_id": doc.meta["doc_id"],
                "title": doc.meta["title"],
                "section": doc.meta["section"],
                "language": doc.meta["language"],
                "effective_date": doc.meta["effective_date"],
                "format": doc.meta["format"],
                "source": doc.source.name,
                "file": name,
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    keep = {e["file"] for e in entries} | {"manifest.json"}
    for stale in out.iterdir():
        if stale.is_file() and stale.name not in keep:
            stale.unlink()
    manifest = {"fictional": True, "company": "Steppelight Technologies", "documents": entries}
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", type=Path, default=ROOT / "data" / "kb_src")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "kb")
    parser.add_argument(
        "--font", type=Path, default=DEFAULT_FONT, help="TTF font with Cyrillic and Kazakh letters"
    )
    args = parser.parse_args()
    register_fonts(args.font)
    entries = build(args.src, args.out)
    counts: dict[str, int] = {}
    for entry in entries:
        counts[str(entry["format"])] = counts.get(str(entry["format"]), 0) + 1
    print(f"Built {len(entries)} documents into {args.out}: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
