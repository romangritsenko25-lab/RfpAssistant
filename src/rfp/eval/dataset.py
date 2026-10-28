"""Loading of an evaluation set from ``data/sets/<name>/``."""

import hashlib
import json
from pathlib import Path

from rfp.eval.metrics import GoldItem
from rfp.models import Question
from rfp.questions import (
    detect_xlsx_layout,
    extract_docx_questions,
    extract_pdf_questions,
    extract_xlsx_questions,
)

SETS_DIR = Path("data/sets")


def set_dir(name: str, root: Path = SETS_DIR) -> Path:
    return root / name


def load_gold(folder: Path) -> tuple[list[GoldItem], str]:
    """Read ``gold.jsonl``; return the items and the set version (first 12 hex chars of its SHA-256)."""
    raw = (folder / "gold.jsonl").read_bytes()
    items = [
        GoldItem.model_validate(json.loads(line)) for line in raw.decode("utf-8").splitlines() if line.strip()
    ]
    return items, hashlib.sha256(raw).hexdigest()[:12]


def extract_set_questions(folder: Path, files: set[str]) -> dict[str, list[Question]]:
    """Run the production question extraction on each source file of the set."""
    return {name: _extract(folder / name) for name in sorted(files)}


def _extract(path: Path) -> list[Question]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        layout = detect_xlsx_layout(path)
        return extract_xlsx_questions(
            path, layout.sheet, layout.question_col, layout.answer_col, layout.header_row
        )
    if suffix == ".docx":
        return extract_docx_questions(path)
    if suffix == ".pdf":
        return extract_pdf_questions(path)
    raise ValueError(f"unsupported question file: {path.name}")
