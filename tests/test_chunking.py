from datetime import date

import pytest

from rfp.chunking import chunk_document
from rfp.models import Document, Section


def make_doc(*texts: str) -> Document:
    return Document(
        doc_id="d1",
        title="Title",
        language="en",
        effective_date=date(2026, 1, 1),
        source_path="d1.md",
        sha256="0" * 64,
        sections=[Section(heading=f"H{i}", text=text, order=i) for i, text in enumerate(texts)],
    )


def words(count: int, start: int = 0) -> str:
    return " ".join(f"w{i}" for i in range(start, start + count))


def test_short_section_is_one_chunk_with_metadata() -> None:
    chunks = chunk_document(make_doc("a short text"), max_words=10, overlap_words=2)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert (chunk.doc_id, chunk.title, chunk.heading, chunk.language) == ("d1", "Title", "H0", "en")
    assert (chunk.effective_date, chunk.order, chunk.text) == (date(2026, 1, 1), 0, "a short text")


def test_long_section_is_cut_with_overlap() -> None:
    chunks = chunk_document(make_doc(words(25)), max_words=10, overlap_words=3)

    assert [c.text.split()[0] for c in chunks] == ["w0", "w7", "w14", "w21"]
    assert all(len(c.text.split()) <= 10 for c in chunks)
    assert chunks[0].text.split()[-3:] == chunks[1].text.split()[:3]
    assert chunks[-1].text.split()[-1] == "w24"


def test_section_of_exactly_max_words_is_not_split() -> None:
    assert len(chunk_document(make_doc(words(10)), max_words=10, overlap_words=3)) == 1


def test_chunks_never_span_sections_and_order_is_global() -> None:
    chunks = chunk_document(make_doc(words(12), words(4, start=100)), max_words=10, overlap_words=2)

    assert [c.heading for c in chunks] == ["H0", "H0", "H1"]
    assert [c.order for c in chunks] == [0, 1, 2]
    assert chunks[-1].text == "w100 w101 w102 w103"


def test_chunking_is_deterministic() -> None:
    doc = make_doc(words(50), words(30))

    assert chunk_document(doc, 12, 4) == chunk_document(doc, 12, 4)


@pytest.mark.parametrize("overlap", [-1, 10, 11])
def test_invalid_overlap_is_rejected(overlap: int) -> None:
    with pytest.raises(ValueError, match="overlap_words"):
        chunk_document(make_doc("text"), max_words=10, overlap_words=overlap)
