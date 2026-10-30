"""Template stubs in answer cells ("[insert response]", "Click here to enter text") count as empty."""

import re

_STUB_WORDS = (
    "insert",
    "enter",
    "type",
    "provide",
    "response",
    "answer",
    "click",
    "tap",
    "vendor",
    "respondent",
    "text",
    "вставьте",
    "введите",
    "ответ",
    "нажмите",
    "жауап",
    "енгізіңіз",
)
_BRACKETED_RE = re.compile(r"^(?:\[[^\]]{1,80}\]|\([^)]{1,80}\)|<[^>]{1,80}>|\{[^}]{1,80}\})$")
_CLICK_RE = re.compile(
    r"^(?:click|tap)\b.{0,40}\b(?:enter|type|add)\b.{0,20}$|^(?:нажмите|введите)\b.{0,60}$"
)
_BLANK_RE = re.compile(r"^[_.\-\s]{3,}$")


def is_placeholder(text: str) -> bool:
    """True for an empty cell or one that only holds a template stub for the answer."""
    cleaned = " ".join(text.split()).casefold()
    if not cleaned or _BLANK_RE.match(cleaned):
        return True
    if _CLICK_RE.match(cleaned):
        return True
    return bool(_BRACKETED_RE.match(cleaned)) and any(word in cleaned for word in _STUB_WORDS)
