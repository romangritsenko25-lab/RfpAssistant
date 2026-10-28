from pydantic import BaseModel, Field

from rfp.models import Question


class QuestionEdits(BaseModel):
    """Manual corrections a reviewer makes to an automatically extracted list."""

    updated: dict[str, str] = Field(default_factory=dict, description="qid -> corrected text")
    removed: set[str] = Field(default_factory=set)
    added: list[Question] = Field(default_factory=list, description="questions the extractor missed")


def merge_edits(extracted: list[Question], edits: QuestionEdits) -> list[Question]:
    """Apply edits to a copy of the list; the result stays in document order where positions are known."""
    merged = [
        question.model_copy(update={"text": edits.updated.get(question.qid, question.text)})
        for question in extracted
        if question.qid not in edits.removed
    ]
    known = {question.qid for question in merged}
    merged.extend(question for question in edits.added if question.qid not in known)
    return sorted(merged, key=_position)


def _position(question: Question) -> tuple[int, int, int]:
    location = question.location
    return (
        location.page or location.block or location.row or 0,
        location.line or location.table_row or 0,
        location.table_col or 0,
    )
