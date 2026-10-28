"""Text rules that tell questions and requirements apart from ordinary prose (ru / kk / en)."""

import re

_NUMBER_RE = re.compile(
    r"^\s*(?P<num>\d+(?:\.\d+)+\.?|\d{1,3}[.)]|\(\d{1,3}\)|[^\W\d_]\))\s+(?P<body>\S.*)$",
    re.DOTALL,
)
_PURE_NUMBER_RE = re.compile(r"^\s*\(?\d+(?:\.\d+)*[.)]?\s*$")

# Modal wording used in requirements; only trusted inside numbered items.
_REQUIREMENT_RE = re.compile(
    r"\b(?:must|shall|should|required)\b"
    r"|\b(?:долж\w+|необходим\w*|требуе\w+|обязан\w*)\b"
    r"|\b(?:тиіс|қажет)\b",
    re.IGNORECASE,
)
# A request addressed to the vendor. Kazakh puts the verb last, so inside numbered items it may appear
# anywhere; in unnumbered paragraphs it must open the sentence to avoid matching ordinary prose.
_REQUEST_VERBS = (
    r"(?:describe|provide|specify|confirm|explain|list|state"
    r"|опишите|укажите|подтвердите|приведите|перечислите|предоставьте|сообщите"
    r"|сипаттаңыз|көрсетіңіз|растаңыз|ұсыныңыз|беріңіз|атаңыз|хабарлаңыз)"
)
_REQUEST_START_RE = re.compile(rf"^(?:please\s+|пожалуйста,?\s+)?{_REQUEST_VERBS}\b", re.IGNORECASE)
_REQUEST_ANYWHERE_RE = re.compile(rf"\b{_REQUEST_VERBS}\b", re.IGNORECASE)
_LONG_PARAGRAPH = 300
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.?!])\s+")


def split_number(text: str) -> tuple[str | None, str]:
    """Split a manual list prefix (``1.``, ``1.1``, ``3)``, ``(4)``, ``a)``) from the text."""
    match = _NUMBER_RE.match(text)
    if match is None:
        return None, text.strip()
    return match.group("num").strip("().").strip(), match.group("body").strip()


def is_number_label(text: str) -> bool:
    """True for a cell that holds only a number such as ``12`` or ``1.3``."""
    return bool(_PURE_NUMBER_RE.match(text))


def is_question(body: str, numbered: bool) -> bool:
    """Decide whether a paragraph is a question or requirement the vendor must answer."""
    if "?" in body or _REQUEST_START_RE.match(body):
        return True
    return numbered and bool(_REQUIREMENT_RE.search(body) or _REQUEST_ANYWHERE_RE.search(body))


def question_text(body: str) -> str:
    """Keep the whole item, but from a long paragraph keep only the sentences that ask something."""
    if len(body) <= _LONG_PARAGRAPH or "?" not in body:
        return body.strip()
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(body) if s.rstrip().endswith("?")]
    return " ".join(sentences).strip()
