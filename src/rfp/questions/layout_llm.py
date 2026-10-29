"""Layout resolution: who decides where the questions are and where the answers go.

Order of authority: the user's explicit columns, then the model's layout map (checked by code), then
header rules. The model is asked once per file (once per group of sheets or pieces of the document
when the file is large). Whatever the model returns is checked against the file itself; a map that
breaks a rule is dropped and the header rules take over.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from openpyxl import load_workbook
from openpyxl.utils import column_index_from_string, get_column_letter
from pydantic import BaseModel, ValidationError

from rfp.llm import ChatClient, LLMUsage
from rfp.models import Question
from rfp.questions.docx_layout import DocxItem, DocxReply, build_questions, render_windows
from rfp.questions.docx_questions import extract_docx_questions
from rfp.questions.layout_map import LayoutMap, SheetMap, map_from_layout
from rfp.questions.layout_repeats import find_repeat_sheets
from rfp.questions.layout_validate import LayoutRejected, check_sheet_map
from rfp.questions.xlsx_layout import detect_xlsx_layout
from rfp.questions.xlsx_questions import extract_xlsx_questions
from rfp.questions.xlsx_snapshot import load_snapshot, render_sheet
from rfp.services.errors import InvalidInputError

log = logging.getLogger(__name__)

PROMPT_BUDGET_CHARS = 30000
MAX_LOGGED_REPLY_CHARS = 2000
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class ManualLayout(NamedTuple):
    """What the user gave explicitly; anything set here is final."""

    sheet: str | None = None
    question_col: str | None = None
    answer_col: str | None = None
    header_row: int | None = None
    number_col: str | None = None

    @property
    def given(self) -> bool:
        return any(
            v is not None for v in (self.question_col, self.answer_col, self.header_row, self.number_col)
        )


@dataclass
class LayoutCall:
    """One model call made to find the layout, for the model request log."""

    usage: LLMUsage | None
    duration_s: float
    error: str | None = None
    reply: str = ""


@dataclass
class LayoutResolution:
    questions: list[Question]
    layout: LayoutMap
    calls: list[LayoutCall] = field(default_factory=list)


class _XlsxReply(BaseModel):
    sheets: list[SheetMap]


# --- XLSX ---------------------------------------------------------------------------------------


def resolve_xlsx(
    path: Path, manual: ManualLayout, *, llm: ChatClient | None, prompt: str | None
) -> LayoutResolution:
    """The questions of an XLSX file and the layout map they came from.

    ``llm`` and ``prompt`` are None when the model must not be used (rules-only mode).
    """
    calls: list[LayoutCall] = []
    if manual.given:
        return _by_rules(path, manual, "manual", calls, None)
    note = None
    if llm is not None and prompt is not None:
        try:
            return _by_model(path, manual.sheet, llm, prompt, calls)
        except LayoutRejected as exc:
            note = str(exc)
        except InvalidInputError:
            raise
        except Exception as exc:
            note = f"the model call failed ({type(exc).__name__})"
            log.warning("Layout call failed: %s", exc)
        if calls and calls[-1].error is None:
            calls[-1].error = note
    try:
        return _by_rules(path, manual, "rules", calls, note)
    except InvalidInputError as exc:
        if note is None:
            raise
        raise InvalidInputError(f"{exc} The model's layout was not used: {note}") from exc


def _by_rules(
    path: Path, manual: ManualLayout, source, calls: list[LayoutCall], note: str | None
) -> LayoutResolution:
    sheets = _sheet_names(path) if manual.sheet is None and source == "rules" else [manual.sheet]
    first_error: InvalidInputError | None = None
    for sheet in sheets:
        try:
            layout = detect_xlsx_layout(
                path,
                sheet,
                header_row=manual.header_row,
                question_col=manual.question_col,
                answer_col=manual.answer_col,
                number_col=manual.number_col,
            )
            questions = extract_xlsx_questions(
                path,
                layout.sheet,
                layout.question_col,
                layout.answer_col,
                layout.header_row,
                layout.number_col,
            )
        except InvalidInputError as exc:
            first_error = first_error or exc
            continue
        if questions or source == "manual":
            return LayoutResolution(
                questions, LayoutMap(source=source, sheets=[map_from_layout(layout)], note=note), calls
            )
    raise first_error or InvalidInputError("No questions were found in the file.")


def _sheet_names(path: Path) -> list[str]:
    workbook = load_workbook(path, read_only=True)
    try:
        return list(workbook.sheetnames)
    finally:
        workbook.close()


def _by_model(
    path: Path, only_sheet: str | None, llm: ChatClient, prompt: str, calls: list[LayoutCall]
) -> LayoutResolution:
    snapshots = load_snapshot(path)
    if only_sheet is not None and only_sheet not in snapshots:
        raise InvalidInputError(f"Sheet '{only_sheet}' not found; available: {', '.join(snapshots)}.")
    # Hidden sheets hold lookups and scoring, not questions for the vendor; only an explicit choice opens one.
    names = [only_sheet] if only_sheet else [n for n, snap in snapshots.items() if not snap.hidden]
    proposed: dict[str, SheetMap] = {}
    for group in _groups([render_sheet(snapshots[n]) for n in names]):
        reply = _ask(llm, prompt, "XLSX", "\n\n".join(group), calls)
        _repair_reply(reply, snapshots)
        try:
            for sheet_map in _XlsxReply.model_validate(reply).sheets:
                proposed[sheet_map.sheet] = sheet_map
        except ValidationError as exc:
            raise LayoutRejected(f"the reply does not fit the schema: {_first_error(exc)}") from exc
    unknown = [n for n in proposed if n not in snapshots]
    if unknown:
        raise LayoutRejected(f"the map names sheets that do not exist: {', '.join(unknown)}")

    proposed = {n: m for n, m in proposed.items() if n in names}  # a sheet we did not ask about is ignored
    checked: list[SheetMap] = []
    left_out: dict[str, str] = {}
    for sheet_map in (m for m in proposed.values() if m.has_questions):
        try:
            checked.append(check_sheet_map(sheet_map, snapshots[sheet_map.sheet]))
        except LayoutRejected as exc:  # one bad sheet does not cost the others
            left_out[sheet_map.sheet] = str(exc)
    if not checked:
        raise LayoutRejected("; ".join(left_out.values()) or "the model found no sheet with questions")
    checked.sort(key=lambda m: names.index(m.sheet))  # workbook order: a repeat comes after its original
    by_sheet: dict[str, list[Question]] = {}
    for sheet_map in checked:
        targets = sheet_map.answer_targets
        assert targets is not None and sheet_map.question_col is not None
        by_sheet[sheet_map.sheet] = extract_xlsx_questions(
            path,
            sheet_map.sheet,
            sheet_map.question_col,
            targets.text_col,
            max(sheet_map.header_row or 0, (sheet_map.first_question_row or 1) - 1),
            sheet_map.number_col,
            last_row=sheet_map.last_question_row,
            skip_rows=frozenset(sheet_map.section_header_rows),
        )
    repeats = find_repeat_sheets(by_sheet)
    questions = [q for sheet, found in by_sheet.items() if sheet not in repeats for q in found]
    if not questions:
        raise LayoutRejected("no questions were read with the model's map")
    questions = [q.model_copy(update={"qid": f"q{n}"}) for n, q in enumerate(questions, 1)]
    done = {
        m.sheet: SheetMap(sheet=m.sheet, has_questions=False, repeat_of=repeats[m.sheet])
        if m.sheet in repeats
        else m
        for m in checked
    }
    for name, reason in left_out.items():
        done[name] = SheetMap(sheet=name, has_questions=False, left_out=reason)
    ordered = [done.get(name) or proposed[name] for name in names if name in proposed]
    return LayoutResolution(questions, LayoutMap(source="llm", sheets=ordered), calls)


def _repair_reply(reply: dict, snapshots: dict) -> None:
    """Small slips of the model that need no judgement, mended before the reply is validated.

    Mark columns that are not at least two distinct column letters are dropped: the model meant a
    drop-down list or a comment column. A sheet with a short-answer column but no text column gets
    the first free column to the right of everything on the sheet; the program titles it, as for a
    table without an answer column.
    """
    for raw in reply.get("sheets") or []:
        targets = raw.get("answer_targets") if isinstance(raw, dict) else None
        if not isinstance(targets, dict):
            continue
        choice = targets.get("choice_cols")
        letters = [c for c in choice.values() if isinstance(c, str) and c.isalpha()] if choice else []
        if choice and (len(letters) != len(choice) or len(set(letters)) != len(letters) or len(letters) < 2):
            targets["choice_cols"] = choice = None
        text = targets.get("text_col")
        if choice and isinstance(text, str) and text.upper() in {c.upper() for c in letters}:
            targets["text_col"] = None  # a column titled with an answer is not free text
        snap = snapshots.get(raw.get("sheet"))
        if snap is None:
            continue
        text = targets.get("text_col")
        has_list = (
            isinstance(text, str)
            and text.isalpha()
            and snap.list_values(column_index_from_string(text.upper()), range(1, snap.max_row + 1))
        )
        if has_list and not targets.get("short_answer_col"):
            # a column with a drop-down list is a short answer, whatever the model called it
            targets["short_answer_col"], targets["text_col"] = text, None
        if targets.get("text_col") or not snap.cells:
            continue
        named = [raw.get("question_col"), raw.get("number_col"), targets.get("short_answer_col")]
        named += [targets.get("source_col"), *(choice.values() if choice else [])]
        used = [column_index_from_string(c.upper()) for c in named if isinstance(c, str) and c.isalpha()]
        targets["text_col"] = get_column_letter(max([*(col for _, col in snap.cells), *used]) + 1)


def _groups(texts: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    size = 0
    for text in texts:
        if groups and size + len(text) > PROMPT_BUDGET_CHARS:
            groups.append([])
            size = 0
        if not groups:
            groups.append([])
        groups[-1].append(text)
        size += len(text)
    return groups


# --- DOCX ---------------------------------------------------------------------------------------


def resolve_docx(path: Path, *, llm: ChatClient | None, prompt: str | None) -> LayoutResolution:
    """The questions of a DOCX file with the places of their answers."""
    calls: list[LayoutCall] = []
    note = None
    if llm is not None and prompt is not None:
        try:
            items: list[DocxItem] = []
            for window in render_windows(path):
                reply = _ask(llm, prompt, "DOCX", window, calls)
                try:
                    items += DocxReply.model_validate(reply).questions
                except ValidationError as exc:
                    raise LayoutRejected(f"the reply does not fit the schema: {_first_error(exc)}") from exc
            questions, paragraphs, cells = build_questions(path, items)
            layout = LayoutMap(source="llm", docx_paragraph_answers=paragraphs, docx_cell_answers=cells)
            return LayoutResolution(questions, layout, calls)
        except LayoutRejected as exc:
            note = str(exc)
        except Exception as exc:
            note = f"the model call failed ({type(exc).__name__})"
            log.warning("Layout call failed: %s", exc)
        if calls and calls[-1].error is None:
            calls[-1].error = note
    questions = extract_docx_questions(path)
    layout = LayoutMap(source="rules", note=note, docx_paragraph_answers=len(questions))
    return LayoutResolution(questions, layout, calls)


# --- the model call -----------------------------------------------------------------------------


def _ask(llm: ChatClient, prompt: str, kind: str, body: str, calls: list[LayoutCall]) -> dict:
    """One layout call; the reply is parsed as a JSON object. Every call is appended to ``calls``."""
    started = time.perf_counter()
    try:
        reply = llm.complete_json(prompt, f"FORMAT: {kind}\n\n{body}")
    except Exception as exc:
        calls.append(LayoutCall(None, time.perf_counter() - started, f"{type(exc).__name__}: {exc}"[:500]))
        raise
    call = LayoutCall(
        reply.usage, time.perf_counter() - started, None, reply.content[:MAX_LOGGED_REPLY_CHARS]
    )
    calls.append(call)
    try:
        data = json.loads(_FENCE_RE.sub("", reply.content.strip()))
    except json.JSONDecodeError as exc:
        raise LayoutRejected("the reply is not valid JSON") from exc
    if not isinstance(data, dict):
        raise LayoutRejected("the reply is not a JSON object")
    return data


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error["loc"])
    return f"{location}: {error['msg']}"
