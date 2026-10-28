"""Build the dev question set from its source file.

Reads ``data/sets/dev/src/questions.json`` (questions, gold answers and the RFP layout) and writes
``questionnaire.xlsx``, ``rfp.docx`` and ``gold.jsonl`` next to it. The output is deterministic:
timestamps are fixed and ZIP containers are re-packed with constant entry times.

Usage:
    uv run python scripts/build_dev_set.py [--src FILE] [--out DIR]
"""

import argparse
import datetime as dt
import io
import json
import re
import sys
import zipfile
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

ROOT = Path(__file__).resolve().parent.parent
DEV_DIR = ROOT / "data" / "sets" / "dev"
ZIP_TIME = (1980, 1, 1, 0, 0, 0)
COLUMN_WIDTHS = {"A": 10, "B": 24, "C": 80, "D": 70}


def normalize_zip(data: bytes, stamp: dt.datetime) -> bytes:
    """Re-pack an OOXML container with constant entry times and a fixed modification date."""
    modified = stamp.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                content = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>" + modified + rb"\g<2>",
                    content,
                )
            entry = zipfile.ZipInfo(info.filename, date_time=ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            dst.writestr(entry, content)
    return out.getvalue()


def number(question_id: str) -> int:
    return int(question_id.split("-")[1])


def build_questionnaire(spec: dict, stamp: dt.datetime) -> bytes:
    meta = spec["meta"]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Questionnaire"
    sheet.append(["ID", "Domain", "Question", "Answer"])
    for q in spec["questions"]:
        if q["file"] == "questionnaire.xlsx":
            sheet.append([q["id"], q["domain"], q["question"], None])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for column, width in COLUMN_WIDTHS.items():
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A2"
    workbook.properties.title = meta["questionnaire_title"]
    workbook.properties.creator = meta["author"]
    workbook.properties.created = stamp
    workbook.properties.modified = stamp
    buffer = io.BytesIO()
    workbook.save(buffer)
    return normalize_zip(buffer.getvalue(), stamp)


def build_rfp(spec: dict, stamp: dt.datetime) -> bytes:
    meta = spec["meta"]
    texts = {q["id"]: q["question"] for q in spec["questions"] if q["file"] == "rfp.docx"}
    document = Document()
    for block in spec["rfp_layout"]:
        match block["type"]:
            case "heading":
                document.add_heading(block["text"], level=block["level"])
            case "paragraph":
                document.add_paragraph(block["text"])
            case "question":
                document.add_paragraph(f"{number(block['id'])}. {texts[block['id']]}")
            case "table":
                table = document.add_table(rows=1, cols=len(block["header"]))
                table.style = "Table Grid"
                for cell, title in zip(table.rows[0].cells, block["header"], strict=True):
                    cell.text = title
                for question_id in block["ids"]:
                    cells = table.add_row().cells
                    cells[0].text = str(number(question_id))
                    cells[1].text = texts[question_id]
            case other:
                raise ValueError(f"unknown RFP block type: {other}")
    props = document.core_properties
    props.title = meta["rfp_title"]
    props.author = meta["author"]
    props.last_modified_by = meta["author"]
    props.created = stamp
    props.modified = stamp
    buffer = io.BytesIO()
    document.save(buffer)
    return normalize_zip(buffer.getvalue(), stamp)


def build_gold(spec: dict) -> str:
    lines = []
    for q in spec["questions"]:
        record = {
            "id": q["id"],
            "file": q["file"],
            "question": q["question"],
            "language": q["language"],
            "answerable": q["gold_answer"] is not None,
            "gold_answer": q["gold_answer"],
            "sources": q["sources"],
            "conflict": q["conflict"],
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", type=Path, default=DEV_DIR / "src" / "questions.json")
    parser.add_argument("--out", type=Path, default=DEV_DIR)
    args = parser.parse_args()
    spec = json.loads(args.src.read_text(encoding="utf-8"))
    stamp = dt.datetime.fromisoformat(spec["meta"]["created"])
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "questionnaire.xlsx").write_bytes(build_questionnaire(spec, stamp))
    (args.out / "rfp.docx").write_bytes(build_rfp(spec, stamp))
    with (args.out / "gold.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(build_gold(spec))
    print(f"Built dev set ({len(spec['questions'])} questions) into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
