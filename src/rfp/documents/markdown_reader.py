import re
from pathlib import Path

from rfp.documents.common import Parsed, SectionCollector, parse_iso_date

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_FENCE = "```"


def read_markdown(path: Path) -> Parsed:
    """Split Markdown at ``#`` headings; a leading ``---`` block supplies metadata."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    meta, body = _split_front_matter(lines)
    collector = SectionCollector()
    in_code = False
    for line in body:
        if line.lstrip().startswith(_FENCE):
            in_code = not in_code
        match = None if in_code else _HEADING_RE.match(line)
        if match:
            collector.start(match.group(2))
        else:
            collector.add(line)
    return Parsed(
        sections=collector.finish(),
        title=meta.get("title"),
        doc_id=meta.get("doc_id"),
        language=meta.get("language") or meta.get("lang"),
        effective_date=parse_iso_date(meta.get("effective_date") or meta.get("date")),
    )


def _split_front_matter(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Parse a flat ``key: value`` header; nested YAML is intentionally not supported."""
    if not lines or lines[0].strip() != "---":
        return {}, lines
    for end, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return _parse_pairs(lines[1:end]), lines[end + 1 :]
    return {}, lines


def _parse_pairs(lines: list[str]) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in lines:
        key, sep, value = line.partition(":")
        if sep and key.strip():
            pairs[key.strip().lower()] = value.strip().strip("\"'")
    return pairs
