"""Split document sections into overlapping, length-limited chunks."""

from rfp.models import Chunk, Document

DEFAULT_MAX_WORDS = 200
DEFAULT_OVERLAP_WORDS = 40


def chunk_document(
    doc: Document, max_words: int = DEFAULT_MAX_WORDS, overlap_words: int = DEFAULT_OVERLAP_WORDS
) -> list[Chunk]:
    """Chunk each section separately; words are the token approximation.

    A section that fits in ``max_words`` becomes one chunk. Longer ones are cut into windows of
    ``max_words`` that share ``overlap_words`` words with the previous window.
    """
    if not 0 <= overlap_words < max_words:
        raise ValueError("overlap_words must be non-negative and smaller than max_words")
    chunks: list[Chunk] = []
    for section in doc.sections:
        for text in _windows(section.text.split(), max_words, overlap_words):
            chunks.append(
                Chunk(
                    doc_id=doc.doc_id,
                    title=doc.title,
                    heading=section.heading,
                    language=doc.language,
                    effective_date=doc.effective_date,
                    order=len(chunks),
                    text=text,
                )
            )
    return chunks


def _windows(words: list[str], max_words: int, overlap_words: int) -> list[str]:
    step = max_words - overlap_words
    windows: list[str] = []
    for start in range(0, len(words), step):
        windows.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return windows
