"""What goes into the short-answer, source and mark cells of a question row.

The model only rates an answer as yes / no / partial / n/a; which sheet value that means is decided
here, against the values the sheet allows. A value the sheet does not allow is never written.
"""

import re
from collections import Counter

from rfp.models import Answer, Location

DEFAULT_MARK = "X"
MAX_MARK_CHARS = 3

_SYNONYMS = {
    "yes": {"yes", "y", "да", "иә", "ия", "true"},
    "no": {"no", "n", "нет", "жоқ", "жок", "false"},
    "partial": {"partial", "partially", "частично", "ішінара"},
    "n/a": {"na", "notapplicable", "не применимо", "неприменимо", "нд", "қолданылмайды"},
}
_CLASS_OF = {_word.replace(" ", ""): cls for cls, words in _SYNONYMS.items() for _word in words}
_TOKEN_RE = re.compile(r"[^\W_]+")


def _normal(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def value_class(value: str) -> str | None:
    """yes / no / partial / n/a for a sheet value or a model rating; None for anything else.

    "Yes - fully" and "Да (полностью)" count as yes: the first word decides when the whole text is unknown.
    """
    whole = _CLASS_OF.get(_normal(value))
    if whole:
        return whole
    tokens = _TOKEN_RE.findall(value.casefold())
    return _CLASS_OF.get(tokens[0]) if tokens and len(tokens[0]) > 1 else None


def match_allowed(short: str | None, allowed: list[str] | None) -> str | None:
    """The allowed value (as written in the sheet) that means ``short``; None when there is none."""
    if not short or not allowed:
        return None
    wanted = value_class(short)
    if wanted is None:
        return None
    matches = [value for value in allowed if value_class(value) == wanted]
    return matches[0] if len(matches) == 1 else None


def short_value(location: Location, answer: Answer) -> str | None:
    """The text for the short-answer cell, or None when nothing is written there."""
    if answer.status != "answered" or not location.short_col:
        return None
    return match_allowed(answer.short, location.allowed_values)


def mark_column(location: Location, answer: Answer) -> str | None:
    """The column that receives the mark for this answer, or None."""
    if answer.status != "answered" or not location.choice_cols:
        return None
    chosen = match_allowed(answer.short, list(location.choice_cols))
    return location.choice_cols[chosen] if chosen else None


def source_value(answer: Answer) -> str | None:
    """The cited documents and sections for the source cell, or None when there is no citation."""
    if answer.status != "answered" or not answer.citations:
        return None
    return "; ".join(f"{c.doc_id}, {c.section}" for c in answer.citations)


def find_mark(sheet, choice_cols: dict[str, str]) -> str:
    """The mark already used in the mark columns of ``sheet`` (a worksheet); a cross when there is none."""
    titles = {_normal(name) for name in choice_cols}
    seen: Counter[str] = Counter()
    for col in choice_cols.values():
        for cell in sheet[f"{col}:{col}"]:
            value = cell.value
            mark = value.strip() if isinstance(value, str) else ""
            if mark and len(mark) <= MAX_MARK_CHARS and _normal(mark) not in titles:
                seen[mark] += 1
    return seen.most_common(1)[0][0] if seen else DEFAULT_MARK
