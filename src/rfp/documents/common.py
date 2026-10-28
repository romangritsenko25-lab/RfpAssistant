"""Pieces shared by the format-specific readers."""

from dataclasses import dataclass, field
from datetime import date

from rfp.models import Section


@dataclass(frozen=True)
class Parsed:
    """What a reader extracted: sections plus whatever metadata the file itself carries."""

    sections: list[Section]
    title: str | None = None
    doc_id: str | None = None
    language: str | None = None
    effective_date: date | None = None


@dataclass
class SectionCollector:
    """Accumulates lines into sections named after the nearest heading (what citations refer to)."""

    _heading: str = ""
    _lines: list[str] = field(default_factory=list)
    _sections: list[Section] = field(default_factory=list)

    def start(self, heading: str) -> None:
        self._flush()
        self._heading = heading.strip()

    def add(self, text: str) -> None:
        if text.strip():
            self._lines.append(text.strip())

    def finish(self) -> list[Section]:
        self._flush()
        return self._sections

    def _flush(self) -> None:
        if self._lines:
            text = "\n".join(self._lines)
            self._sections.append(Section(heading=self._heading, text=text, order=len(self._sections)))
            self._lines = []


def parse_iso_date(value: object) -> date | None:
    """Parse ``YYYY-MM-DD`` (or a longer ISO timestamp); return None for anything else."""
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None
