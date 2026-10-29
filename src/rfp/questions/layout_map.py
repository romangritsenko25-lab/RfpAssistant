"""The layout map: where the questions are and where each part of an answer goes.

For XLSX the map has one entry per sheet. It names the targets of every part of an answer (short
value, full text, source) even though only the text column is written today, so that a later stage
can start filling the others without changing the map. The map comes from the model (``llm``), from
header rules (``rules``) or from the user (``manual``); in every case it is verified by code before use.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from rfp.questions.xlsx_layout import XlsxLayout

COLUMN_RE = re.compile(r"^[A-Z]{1,3}$")
LayoutSource = Literal["llm", "rules", "manual"]


def _column(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if not COLUMN_RE.match(text):
        raise ValueError(f"'{value}' is not a column letter")
    return text


class AnswerTargets(BaseModel):
    """Cells of one question row that receive the parts of its answer."""

    text_col: str = Field(description="Column for the full answer text")
    short_answer_col: str | None = Field(
        default=None, description="Column for a short value (Yes/No, a choice)"
    )
    allowed_values: list[str] | None = Field(
        default=None, description="Values the short answer may take, when the column has a drop-down list"
    )
    source_col: str | None = Field(default=None, description="Column for the source of the answer")
    choice_cols: dict[str, str] | None = Field(
        default=None,
        description="Value -> column, when the answer is a mark (a cross) in one of several columns",
    )

    @field_validator("text_col", "short_answer_col", "source_col", mode="before")
    @classmethod
    def _letters(cls, value: object) -> str | None:
        return _column(value)

    @field_validator("choice_cols", mode="before")
    @classmethod
    def _choice_letters(cls, value: object) -> dict[str, str] | None:
        if value is None or value == {}:
            return None
        if not isinstance(value, dict):
            raise ValueError("choice_cols must map each value to a column letter")
        cleaned: dict[str, str] = {}
        for name, col in value.items():
            letter = _column(col)
            if not str(name).strip() or letter is None:
                raise ValueError("choice_cols needs a value and a column letter in every entry")
            cleaned[str(name).strip()] = letter
        return cleaned

    @field_validator("text_col")
    @classmethod
    def _text_required(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("text_col is required")
        return value

    def columns(self) -> list[str]:
        marks = list((self.choice_cols or {}).values())
        return [c for c in (self.short_answer_col, self.text_col, self.source_col, *marks) if c]


class SheetMap(BaseModel):
    sheet: str
    has_questions: bool = True
    header_row: int | None = Field(default=None, ge=0, description="0 when the sheet has no header row")
    question_col: str | None = None
    number_col: str | None = None
    section_header_rows: list[int] = Field(default_factory=list, description="Rows that only title a section")
    first_question_row: int | None = Field(default=None, ge=1)
    last_question_row: int | None = Field(default=None, ge=1)
    answer_targets: AnswerTargets | None = None
    # Set by code, never by the model:
    answer_header: str | None = Field(default=None, description="Title for a text column the sheet lacks")
    skipped_rows: int = Field(default=0, description="Section-header rows left out of the questions")
    repeat_of: str | None = Field(
        default=None, description="Sheet whose questions this one repeats; its rows are not questions"
    )
    left_out: str | None = Field(default=None, description="Why the model's map of this sheet was not used")

    @field_validator("question_col", "number_col", mode="before")
    @classmethod
    def _letters(cls, value: object) -> str | None:
        return _column(value)

    @model_validator(mode="after")
    def _complete(self) -> "SheetMap":
        if self.has_questions and (self.question_col is None or self.answer_targets is None):
            raise ValueError(f"sheet '{self.sheet}' has questions but no question column or answer targets")
        return self


class LayoutMap(BaseModel):
    source: LayoutSource
    sheets: list[SheetMap] = Field(default_factory=list)
    note: str | None = Field(default=None, description="Why the model's map was not used, if it was not")
    docx_paragraph_answers: int = 0
    docx_cell_answers: int = 0

    def sheets_with_questions(self) -> list[SheetMap]:
        return [s for s in self.sheets if s.has_questions]


def map_from_layout(layout: XlsxLayout, skipped_rows: int = 0) -> SheetMap:
    """The sheet map equivalent of a layout found by header rules or given by the user."""
    return SheetMap(
        sheet=layout.sheet,
        header_row=layout.header_row,
        question_col=layout.question_col,
        number_col=layout.number_col,
        answer_targets=AnswerTargets(text_col=layout.answer_col),
        answer_header=layout.answer_header,
        skipped_rows=skipped_rows,
    )
