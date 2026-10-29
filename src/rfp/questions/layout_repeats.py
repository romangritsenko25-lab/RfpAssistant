"""Sheets that repeat the questions of an earlier sheet (change logs, crosswalks, analyst copies).

Such a sheet is no place for answers: its rows are copies, and answering them would fill the same
question twice. Whatever the model said about it, the sheet is left out when most of its question
texts already stand on a sheet that comes before it in the workbook.
"""

from rfp.models import Question

REPEAT_SHARE = 0.5
MIN_REPEATED = 2


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


def find_repeat_sheets(by_sheet: dict[str, list[Question]]) -> dict[str, str]:
    """Sheet name -> name of the earlier sheet it repeats. ``by_sheet`` is in workbook order."""
    kept: dict[str, set[str]] = {}
    repeats: dict[str, str] = {}
    for sheet, questions in by_sheet.items():
        texts = {_key(q.text) for q in questions}
        best, closest = None, 0
        for other, other_texts in kept.items():
            common = len(texts & other_texts)
            if common > closest:
                best, closest = other, common
        shared = len(texts & set().union(*kept.values()))  # copies may be spread over several sheets
        if best is not None and shared >= MIN_REPEATED and shared >= REPEAT_SHARE * len(texts):
            repeats[sheet] = best
        else:
            kept[sheet] = texts
    return repeats
