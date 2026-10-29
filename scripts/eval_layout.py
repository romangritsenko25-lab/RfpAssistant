"""Measure the layout map on the public questionnaires in ``data/public/<slug>/``.

For every file the service's own path is run (``resolve_xlsx`` / ``resolve_docx``) in model mode
and/or header-rules mode, and the result is compared with a reference derived from the file by
independent rules (ID patterns, table shapes) and cross-checked against the counts in ``truth.json``.
The report holds numbers and cell addresses only, never question texts: the files may not be
redistributed.

Usage:
    uv run python scripts/eval_layout.py [--mode llm|rules|both] [--label NAME] [--baseline JSON]

Model mode makes real calls (key from ``.env``) and costs a few cents. Results are also saved as JSON
in ``reports/raw/`` (not committed); ``--baseline`` adds a before/after comparison to the report.
"""

import argparse
import datetime as dt
import json
import re
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as open_docx
from docx.table import Table
from openpyxl import load_workbook

from rfp.config import Settings
from rfp.docx_blocks import iter_blocks
from rfp.llm import OpenAIChatClient
from rfp.questions import ManualLayout, resolve_docx, resolve_xlsx
from rfp.questions.docx_questions import unique_cells

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "data" / "public"
REPORTS = ROOT / "reports"
THRESHOLD = 95.0
ID_RE = re.compile(r"^[A-Z&]{2,4}-\d+(\.\d+)?$")
INFO_PREFIXES = ("GNRL", "DATE")  # label/value rows that carry an ID but are not questions


# --- the reference ------------------------------------------------------------------------------


@dataclass(frozen=True)
class SheetRef:
    """What a correct map says about one sheet that holds questions."""

    sheet: str
    id_col: str
    question_col: str
    text_col: str
    short_col: str | None = None
    allowed_base: frozenset[str] = frozenset()  # values the list must contain
    allowed_full: frozenset[str] = frozenset()  # values the list may contain
    choice_cols: dict[str, str] = field(default_factory=dict)  # value -> column, answers marked with a cross


@dataclass(frozen=True)
class XlsxRef:
    sheets: tuple[SheetRef, ...]


@dataclass(frozen=True)
class DocxRef:
    kind: str  # "txdot" | "cdt" | "ut"


def _values(*items: str) -> frozenset[str]:
    return frozenset(items)


HECVAT_SHEETS = (
    "START HERE",
    "Organization",
    "Product",
    "Infrastructure",
    "IT Accessibility",
    "Case-Specific",
    "AI",
    "Privacy",
)

REFERENCES: dict[str, XlsxRef | DocxRef] = {
    "csa-caiq-v3-1": XlsxRef(
        (SheetRef("CAIQ v3.1", "C", "E", "Z", choice_cols={"Yes": "W", "No": "X", "Not Applicable": "Y"}),)
    ),
    "csa-caiq-v4-1": XlsxRef(
        (
            SheetRef(
                "CAIQv4.1.0",
                "A",
                "B",
                "E",
                "C",
                _values("Yes", "No", "NA"),
                _values("Yes", "No", "NA"),
            ),
        )
    ),
    "hecvat-lite-iu-mirror": XlsxRef(
        (SheetRef("HECVAT - Lite", "A", "B", "D", "C", _values("Yes", "No"), _values("Yes", "No")),)
    ),
    "hecvat-4-16-github-mirror": XlsxRef(
        tuple(
            SheetRef(
                name,
                "A",
                "B",
                "D",
                "C",
                _values("Yes", "No"),
                _values("Yes", "No", "N/A", "Mark as Compliant", "Mark as Non-Compliant"),
            )
            for name in HECVAT_SHEETS
        )
    ),
    "txdot-security-questionnaire": DocxRef("txdot"),
    "ca-cdt-rfi-managed-security": DocxRef("cdt"),
    "ut-system-3rd-party-intake": DocxRef("ut"),
}


def xlsx_expected_rows(path: Path, ref: SheetRef) -> set[int]:
    """Rows whose ID cell looks like a question ID and whose question cell is not empty."""
    workbook = load_workbook(path, data_only=True)
    try:
        sheet = workbook[ref.sheet]
        rows = set()
        for row in range(1, (sheet.max_row or 0) + 1):
            ident = str(sheet[f"{ref.id_col}{row}"].value or "").strip()
            is_id = ID_RE.match(ident) or re.match(r"^[A-Z]{4}-\d+", ident)
            if is_id and not ident.startswith(INFO_PREFIXES) and sheet[f"{ref.question_col}{row}"].value:
                rows.add(row)
        return rows
    finally:
        workbook.close()


@dataclass
class DocxExpected:
    keys: dict[tuple[int, int | None], int | None]  # (block, table row or None) -> question cell column
    answer: tuple[int, int] | None  # (row offset, column) of the answer cell; None for "no separate cell"
    answer_checked: bool


def docx_expected(path: Path, kind: str) -> DocxExpected:
    blocks = list(iter_blocks(open_docx(str(path))))
    keys: dict[tuple[int, int | None], int | None] = {}
    if kind == "txdot":
        tables = [i for i, b in enumerate(blocks) if isinstance(b, Table)][:4]
        for index in tables:
            for row_index, row in enumerate(blocks[index].rows):
                cells = unique_cells(row)
                if len(cells) < 3:
                    continue
                ident, text = cells[0][1].text.strip(), cells[1][1].text.strip()
                if ident and len(text) > 15 and not text.startswith(("If No", "Comments")):
                    keys[(index, row_index)] = cells[1][0]
        return DocxExpected(keys, (0, 2), True)
    for index, block in enumerate(blocks):
        if isinstance(block, Table):
            if kind != "ut":
                continue
            for row_index, row in enumerate(block.rows):
                for col, cell in unique_cells(row):
                    text = cell.text.strip()
                    if re.match(r"^\d+\.\s", text) or "?" in text:
                        keys[(index, row_index)] = col
        elif "?" in block.text:
            keys[(index, None)] = None
    return DocxExpected(keys, None, kind == "cdt")


# --- running the service path --------------------------------------------------------------------


def run_one(path: Path, mode: str, client, prompt: str) -> dict:
    """Resolve the layout of one file; returns the data the report needs, without any question text."""
    llm, text = (client, prompt) if mode == "llm" else (None, None)
    outcome: dict = {"mode": mode, "error": None}
    try:
        if path.suffix == ".xlsx":
            resolution = resolve_xlsx(path, ManualLayout(), llm=llm, prompt=text)
        else:
            resolution = resolve_docx(path, llm=llm, prompt=text)
    except Exception as exc:
        outcome["error"] = f"{type(exc).__name__}: {str(exc)[:700]}"
        return outcome
    layout = resolution.layout
    outcome["source"] = layout.source
    outcome["note"] = layout.note
    outcome["calls"] = len(resolution.calls)
    outcome["replies"] = [c.reply for c in resolution.calls]  # structure only; kept in the raw JSON
    outcome["cost_usd"] = sum(c.usage.cost_usd or 0.0 for c in resolution.calls if c.usage)
    outcome["questions"] = [q.location.model_dump(exclude_none=True) for q in resolution.questions]
    outcome["sheets"] = [
        {
            "sheet": m.sheet,
            "question_col": m.question_col,
            "text_col": m.answer_targets.text_col,
            "short_col": m.answer_targets.short_answer_col,
            "allowed": m.answer_targets.allowed_values,
            "choice_cols": getattr(m.answer_targets, "choice_cols", None),
        }
        for m in layout.sheets_with_questions()
        if m.answer_targets
    ]
    return outcome


# --- scoring -------------------------------------------------------------------------------------


def score_xlsx(path: Path, ref: XlsxRef, outcome: dict) -> dict:
    expected = {r.sheet: xlsx_expected_rows(path, r) for r in ref.sheets}
    refs = {r.sheet: r for r in ref.sheets}
    total = sum(len(rows) for rows in expected.values())
    found = extra_repeat = extra_other = question_ok = text_ok = 0
    seen: set[tuple[str, int]] = set()
    for loc in outcome["questions"]:
        key = (loc["sheet"], loc["row"])
        if key in seen:
            extra_other += 1
            continue
        seen.add(key)
        if loc["sheet"] not in refs:
            extra_repeat += 1
        elif loc["row"] not in expected[loc["sheet"]]:
            extra_other += 1
        else:
            found += 1
            question_ok += loc.get("question_col") == refs[loc["sheet"]].question_col
            text_ok += loc.get("answer_col") == refs[loc["sheet"]].text_col
    maps = {m["sheet"]: m for m in outcome["sheets"]}
    short_ok = allowed_ok = choice_ok = 0
    short_n = sum(1 for r in ref.sheets if r.short_col)
    choice_n = sum(1 for r in ref.sheets if r.choice_cols)
    for sheet_ref in ref.sheets:
        got = maps.get(sheet_ref.sheet)
        if got is None:
            continue
        if sheet_ref.short_col:
            short_ok += got["short_col"] == sheet_ref.short_col
            listed = set(got["allowed"] or ())
            allowed_ok += bool(listed) and sheet_ref.allowed_base <= listed <= sheet_ref.allowed_full
        if sheet_ref.choice_cols:
            choice_ok += (got["choice_cols"] or {}) == sheet_ref.choice_cols
    return {
        "expected": total,
        "found": found,
        "extra_repeat": extra_repeat,
        "extra_other": extra_other,
        "question_col": [question_ok, found],
        "text_col": [text_ok, found],
        "short_col": [short_ok, short_n],
        "allowed": [allowed_ok, short_n],
        "choice": [choice_ok, choice_n],
    }


def score_docx(path: Path, ref: DocxRef, outcome: dict) -> dict:
    expected = docx_expected(path, ref.kind)
    found = extra = question_ok = answer_ok = 0
    seen: set[tuple[int, int | None]] = set()
    for loc in outcome["questions"]:
        key = (loc["block"], loc.get("table_row"))
        if key in seen or key not in expected.keys:
            extra += 1
            continue
        seen.add(key)
        found += 1
        question_ok += loc.get("table_col") == expected.keys[key]
        if expected.answer_checked:
            want = expected.answer
            got = (
                (loc["answer_table_row"] - loc["table_row"], loc["answer_table_col"])
                if "answer_table_row" in loc
                else None
            )
            answer_ok += got == want
    return {
        "expected": len(expected.keys),
        "found": found,
        "extra_repeat": 0,
        "extra_other": extra,
        "question_col": [question_ok, found],
        "text_col": [answer_ok, found if expected.answer_checked else 0],
        "short_col": [0, 0],
        "allowed": [0, 0],
        "choice": [0, 0],
    }


def truth_count(slug: str) -> int | None:
    return json.loads((PUBLIC / slug / "truth.json").read_text(encoding="utf-8")).get("question_count")


def evaluate(slug: str, modes: list[str], client, prompt: str) -> list[dict]:
    folder = PUBLIC / slug
    path = next(p for p in folder.iterdir() if p.suffix in (".xlsx", ".docx"))
    ref = REFERENCES[slug]
    results = []
    for mode in modes:
        outcome = run_one(path, mode, client, prompt)
        result = {"slug": slug, "file_type": path.suffix[1:], "truth_count": truth_count(slug), **outcome}
        if outcome["error"] is None:
            scorer = score_xlsx if isinstance(ref, XlsxRef) else score_docx
            result["score"] = scorer(path, ref, outcome)
        results.append(result)
        print(f"{slug} [{mode}]: {_summary(result)}", flush=True)
    return results


def _summary(result: dict) -> str:
    if result["error"]:
        return f"ERROR {result['error']}"
    s = result["score"]
    return f"{s['found']}/{s['expected']} found, {s['extra_repeat'] + s['extra_other']} extra"


# --- the report ----------------------------------------------------------------------------------


def _pct(found: int, expected: int) -> float:
    return 100.0 * found / expected if expected else 0.0


def _ratio(pair: list[int]) -> str:
    done, total = pair
    return "n/a" if total == 0 else f"{done}/{total}"


def _row(result: dict) -> str:
    head = f"| {result['slug']} | {result['mode']} |"
    if result["error"]:
        return f"{head} error: {result['error']} | | | | | | | |"
    s = result["score"]
    pct = _pct(s["found"], s["expected"])
    mark = "ok" if pct >= THRESHOLD else "BELOW"
    used = result["source"] + (" (fallback)" if result["mode"] == "llm" and result["source"] != "llm" else "")
    return (
        f"{head} {used} | {s['found']}/{s['expected']} ({pct:.1f}%, {mark}) | "
        f"{s['extra_repeat']} / {s['extra_other']} | {_ratio(s['question_col'])} | {_ratio(s['text_col'])} | "
        f"{_ratio(s['short_col'])} / {_ratio(s['allowed'])} | {_ratio(s['choice'])} | "
        f"{result['cost_usd']:.4f} |"
    )


TABLE_HEAD = (
    "| file | mode | layout used | found / reference | extra: repeat sheets / other | question column "
    "| answer text target | short answer column / values | choice columns | cost, USD |\n"
    "|---|---|---|---|---|---|---|---|---|---|"
)


def _found(result: dict | None) -> str:
    if result is None or "score" not in result:
        return "no result (error)"
    return f"{result['score']['found']}/{result['score']['expected']}"


def _extra(result: dict | None) -> str:
    if result is None or "score" not in result:
        return "-"
    return str(result["score"]["extra_repeat"] + result["score"]["extra_other"])


def _compare(before: list[dict], after: list[dict]) -> list[str]:
    lines = [
        "| file | mode | found before | found after | extra before | extra after |",
        "|---|---|---|---|---|---|",
    ]
    old = {(r["slug"], r["mode"]): r for r in before}
    for result in after:
        prev = old.get((result["slug"], result["mode"]))
        lines.append(
            f"| {result['slug']} | {result['mode']} | {_found(prev)} | {_found(result)} | "
            f"{_extra(prev)} | {_extra(result)} |"
        )
    return lines


def write_report(results: list[dict], model: str, label: str | None, baseline: list[dict] | None) -> Path:
    today = dt.date.today().isoformat()
    path = REPORTS / (f"layout-{today}-{label}.md" if label else f"layout-{today}.md")
    cost = sum(r.get("cost_usd", 0.0) for r in results)
    calls = sum(r.get("calls", 0) for r in results)
    lines = [
        f"# Layout map on public questionnaires, {today}" + (f" ({label})" if label else ""),
        "",
        f"Model for the layout call: `{model}`. Reference: derived from each file by ID patterns and table "
        "shapes, checked against `truth.json` counts. Numbers and cell addresses only: no question texts.",
        f"Threshold from the specification: at least {THRESHOLD:.0f}% of the reference questions found.",
        "",
        'Columns: `extra` counts "questions" outside the reference, split into rows on sheets that must '
        "not hold questions (repeat sheets) and other rows (section titles, info rows, duplicates). "
        "The three target columns count questions (or sheets for short answer, values and choice columns) "
        "that match the reference.",
        "",
        TABLE_HEAD,
        *(_row(r) for r in results),
        "",
    ]
    for mode in sorted({r["mode"] for r in results}):
        rows = [r for r in results if r["mode"] == mode and "score" in r]
        found = sum(r["score"]["found"] for r in rows)
        expected = sum(r["score"]["expected"] for r in rows)
        passed = sum(_pct(r["score"]["found"], r["score"]["expected"]) >= THRESHOLD for r in rows)
        lines.append(
            f"Total, mode `{mode}`: {found}/{expected} ({_pct(found, expected):.1f}%); "
            f"files at or above {THRESHOLD:.0f}%: {passed} of {len(rows)}."
        )
    lines += ["", f"Model calls: {calls}, cost {cost:.4f} USD."]
    if baseline:
        lines += ["", "## Against the baseline", "", *_compare(baseline, results)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mode", choices=["llm", "rules", "both"], default="both")
    parser.add_argument("--label", help="suffix of the report name and of the saved JSON")
    parser.add_argument("--only", action="append", metavar="SLUG", help="run only this file (repeatable)")
    parser.add_argument("--baseline", type=Path, help="JSON of an earlier run to compare with")
    args = parser.parse_args()
    modes = ["llm", "rules"] if args.mode == "both" else [args.mode]

    sys.stdout.reconfigure(encoding="utf-8")  # error messages may quote Cyrillic or Kazakh headers
    warnings.simplefilter("ignore")  # openpyxl warns about the extensions it drops
    settings = Settings()
    model = settings.layout_model or settings.llm_model
    client = OpenAIChatClient(settings, model=model) if "llm" in modes else None
    prompt = settings.layout_prompt_path.read_text(encoding="utf-8") if "llm" in modes else ""

    results: list[dict] = []
    for slug in REFERENCES:
        if (PUBLIC / slug).is_dir() and (not args.only or slug in args.only):
            results += evaluate(slug, modes, client, prompt)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    report = write_report(results, model, args.label, baseline)
    raw = REPORTS / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / f"layout-{args.label or 'run'}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
