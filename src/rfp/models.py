"""Shared data models used across ingestion, question extraction, answering and export."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Section(BaseModel):
    heading: str
    text: str
    order: int


class Document(BaseModel):
    doc_id: str
    title: str
    language: str
    effective_date: date | None = None
    source_path: str
    sha256: str
    sections: list[Section]


class Chunk(BaseModel):
    doc_id: str
    title: str
    heading: str
    language: str
    effective_date: date | None = None
    order: int
    text: str


class Location(BaseModel):
    """Where a question lives in the source file; which fields are set depends on the format.

    XLSX: ``sheet``, ``row`` (1-based) and ``answer_col`` (letter).
    DOCX: ``block`` (index of the paragraph or table among body blocks); for a table cell also
    ``table_row`` and ``table_col`` (0-based).
    PDF: ``page`` and ``line`` (both 1-based).
    """

    sheet: str | None = None
    row: int | None = None
    answer_col: str | None = None
    block: int | None = None
    table_row: int | None = None
    table_col: int | None = None
    page: int | None = None
    line: int | None = None


class Question(BaseModel):
    qid: str
    text: str
    number: str | None = None
    location: Location


class Citation(BaseModel):
    doc_id: str
    section: str
    snippet: str


AnswerStatus = Literal["answered", "no_data", "needs_review"]


class Answer(BaseModel):
    qid: str
    text: str
    status: AnswerStatus
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[Citation] = Field(default_factory=list)
