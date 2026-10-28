"""Hard checks of a sheet map against the workbook itself.

The model proposes; this code decides. A map that breaks any rule is rejected as a whole, and the
caller falls back to header rules.
"""

from openpyxl.utils import column_index_from_string

from rfp.questions.layout_map import SheetMap
from rfp.questions.xlsx_layout import answer_title
from rfp.questions.xlsx_snapshot import SheetSnapshot

MAX_PROBLEMS = 5


class LayoutRejected(ValueError):
    """The map is unsafe or does not match the file; the message lists what is wrong."""


def check_sheet_map(sheet_map: SheetMap, snap: SheetSnapshot) -> SheetMap:
    """Return the map completed from the file (rows, skipped sections, new column title) or raise.

    Rules: the answer columns differ from the question and number columns and from each other; the
    declared rows lie inside the sheet and the question cells hold text; there is at least one
    question; answer cells never hold or share a merged cell with their question; an answer column
    that is already mostly filled is refused; allowed values come from the sheet's drop-down list.
    """
    targets = sheet_map.answer_targets
    assert targets is not None and sheet_map.question_col is not None  # guaranteed by SheetMap
    where = f"sheet '{snap.name}'"
    problems: list[str] = []

    named = [("question", sheet_map.question_col), ("number", sheet_map.number_col)]
    named += [("short answer", targets.short_answer_col), ("answer text", targets.text_col)]
    named += [("source", targets.source_col)]
    seen: dict[str, str] = {}
    for role, col in named:
        if col is None:
            continue
        if col in seen:
            problems.append(f"{where}: the {role} column {col} is also the {seen[col]} column")
        seen.setdefault(col, role)

    question_idx = column_index_from_string(sheet_map.question_col)
    header = sheet_map.header_row or 0
    first = sheet_map.first_question_row or header + 1
    last = sheet_map.last_question_row or snap.max_row
    if header > snap.max_row:
        problems.append(f"{where}: header row {header} is below the last row {snap.max_row}")
    if last > snap.max_row:
        problems.append(f"{where}: last question row {last} is below the last row {snap.max_row}")
    if first <= header:
        problems.append(f"{where}: the first question row {first} is not below the header row {header}")
    if first > last:
        problems.append(f"{where}: the first question row {first} is after the last one {last}")
    outside = [r for r in sheet_map.section_header_rows if not 1 <= r <= snap.max_row]
    if outside:
        problems.append(f"{where}: section header rows {outside} are outside the sheet")
    if problems:
        raise LayoutRejected("; ".join(problems[:MAX_PROBLEMS]))

    section = {r for r in sheet_map.section_header_rows if first <= r <= last}
    for row in range(first, last + 1):
        merged = snap.merged_at(row, question_idx)
        if snap.text(row, question_idx) and merged is not None and merged.max_col > merged.min_col:
            section.add(row)  # a title stretched across the row is never a question
    question_rows = [r for r in range(first, last + 1) if r not in section and snap.text(r, question_idx)]
    if not question_rows:
        problems.append(f"{where}: no question text in column {sheet_map.question_col}, rows {first}-{last}")
    for edge, label in ((sheet_map.first_question_row, "first"), (sheet_map.last_question_row, "last")):
        if edge is not None and edge not in section and not snap.text(edge, question_idx):
            problems.append(f"{where}: the {label} question row {edge} has no question text")
    if problems:
        raise LayoutRejected("; ".join(problems[:MAX_PROBLEMS]))

    for col in targets.columns():
        problems += _check_target_column(snap, col, question_idx, question_rows)
    allowed, allowed_ok = _check_allowed_values(
        snap, targets.short_answer_col, targets.allowed_values, first, last
    )
    if not allowed_ok:
        problems.append(
            f"{where}: allowed values of column {targets.short_answer_col} are not in its drop-down list"
        )
    if problems:
        raise LayoutRejected("; ".join(problems[:MAX_PROBLEMS]))

    header_cells = tuple(snap.text(header, c) or None for c in range(1, snap.max_col + 1))
    text_idx = column_index_from_string(targets.text_col)
    new_title = (
        answer_title(header_cells, question_idx) if header >= 1 and not snap.text(header, text_idx) else None
    )
    new_targets = targets.model_copy(update={"allowed_values": allowed or None})
    return sheet_map.model_copy(
        update={
            "header_row": header,
            "first_question_row": question_rows[0],
            "last_question_row": question_rows[-1],
            "section_header_rows": sorted(section),
            "skipped_rows": sum(1 for r in section if snap.text(r, question_idx)),
            "answer_targets": new_targets,
            "answer_header": new_title,
        }
    )


def _check_target_column(
    snap: SheetSnapshot, col: str, question_idx: int, question_rows: list[int]
) -> list[str]:
    index = column_index_from_string(col)
    where = f"sheet '{snap.name}', column {col}"
    filled = 0
    for row in question_rows:
        question = snap.text(row, question_idx)
        cell = snap.text(row, index)
        if cell and question in cell:
            return [f"{where}: cell {col}{row} holds the question text"]
        area = snap.merged_at(row, index)
        if area is not None and area.contains(row, question_idx):
            return [f"{where}: cell {col}{row} is merged with the question cell"]
        filled += bool(cell)
    if filled >= 2 and filled * 2 > len(question_rows):
        return [f"{where}: already holds data in {filled} of {len(question_rows)} question rows"]
    return []


def _check_allowed_values(
    snap: SheetSnapshot, short_col: str | None, allowed: list[str] | None, first: int, last: int
) -> tuple[list[str] | None, bool]:
    """The allowed values to keep and whether they agree with the sheet's drop-down list.

    Without a drop-down list over the column the values cannot be verified and are dropped.
    """
    if not allowed or short_col is None:
        return None, True
    listed = snap.list_values(column_index_from_string(short_col), range(first, last + 1))
    if listed is None:
        return None, True
    if {v.strip() for v in allowed} <= listed:
        return list(allowed), True
    return None, False
