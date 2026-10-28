"""Language detection for knowledge-base documents (kk / ru / en only)."""

import re

_KAZAKH_LETTERS = frozenset("әғқңөұүһіӘҒҚҢӨҰҮҺІ")
_CYRILLIC_RE = re.compile(r"[а-яёА-ЯЁ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")
_SAMPLE_CHARS = 5000
_KAZAKH_SHARE = 0.02


def detect_language(text: str) -> str:
    """Guess ``kk``, ``ru`` or ``en`` from the letters used in the first part of the text."""
    sample = text[:_SAMPLE_CHARS]
    kazakh = sum(1 for ch in sample if ch in _KAZAKH_LETTERS)
    cyrillic = len(_CYRILLIC_RE.findall(sample)) + kazakh
    latin = len(_LATIN_RE.findall(sample))
    if cyrillic and kazakh / cyrillic >= _KAZAKH_SHARE:
        return "kk"
    return "ru" if cyrillic > latin else "en"


def normalize_language(value: str | None) -> str | None:
    """Reduce a metadata value such as ``ru-RU`` to a two-letter code."""
    if not value or not value.strip():
        return None
    return value.strip().lower().replace("_", "-").split("-")[0]
