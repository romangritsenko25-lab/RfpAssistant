from pathlib import Path

import pytest

from rfp.models import Location, Question
from rfp.questions import (
    QuestionEdits,
    extract_docx_questions,
    extract_pdf_questions,
    extract_xlsx_questions,
    merge_edits,
)
from rfp.questions.rules import is_question, question_text, split_number
from tests import factories


@pytest.mark.parametrize(
    ("text", "number", "body"),
    [
        ("1. Describe it", "1", "Describe it"),
        ("1.1 Do you test?", "1.1", "Do you test?"),
        ("2) Must support SSO", "2", "Must support SSO"),
        ("(3) Укажите срок", "3", "Укажите срок"),
        ("a) Provide a list", "a", "Provide a list"),
        ("2024 was a good year", None, "2024 was a good year"),
        ("No number here", None, "No number here"),
    ],
)
def test_split_number(text: str, number: str | None, body: str) -> None:
    assert split_number(text) == (number, body)


@pytest.mark.parametrize(
    ("body", "numbered", "expected"),
    [
        ("Is there a DR plan?", False, True),
        ("Describe the process.", False, True),
        ("The vendor must be certified.", True, True),
        ("The vendor must be certified.", False, False),
        ("Company founded in 2012.", True, False),
    ],
)
def test_is_question(body: str, numbered: bool, expected: bool) -> None:
    assert is_question(body, numbered) is expected


def test_question_text_keeps_only_asking_sentences_of_long_paragraph() -> None:
    assert question_text(factories.LONG_PARAGRAPH) == factories.LONG_QUESTION
    assert question_text("Short text.") == "Short text."


def test_xlsx_questions_keep_number_and_location(questionnaire_xlsx: Path) -> None:
    questions = extract_xlsx_questions(
        questionnaire_xlsx, "Questionnaire", question_col="B", answer_col="C", header_row=2, number_col="A"
    )

    assert [q.number for q in questions] == ["IAM-01", "IAM-02", "BCR-01"]
    assert [q.location.row for q in questions] == [3, 4, 6]
    assert {(q.location.sheet, q.location.answer_col) for q in questions} == {("Questionnaire", "C")}
    assert questions[2].text == "Деректерді сақтау мерзімі қандай?"
    assert [q.qid for q in questions] == ["q1", "q2", "q3"]


def test_xlsx_questions_ignore_rows_above_header(questionnaire_xlsx: Path) -> None:
    questions = extract_xlsx_questions(questionnaire_xlsx, "Questionnaire", "B", "C", header_row=1)

    assert questions[0].text == "Question"  # header row 2 is data when header_row=1
    assert all(q.number is None for q in questions)


def test_docx_questions_found_in_document_order(rfp_docx: Path) -> None:
    questions = extract_docx_questions(rfp_docx)

    assert [q.number for q in questions[:8]] == ["1", "1.1", "1.2", "2", "3", "4", "5", "6"]
    blocks = [q.location.block for q in questions]
    assert blocks == sorted(blocks)
    assert questions[3].text == "The vendor must support single sign-on (SSO)."


def test_docx_word_numbering_is_reconstructed(rfp_docx: Path) -> None:
    by_text = {q.text: q for q in extract_docx_questions(rfp_docx)}

    assert by_text["The solution shall provide audit logs."].number == "1"
    assert by_text["Data must be stored in Kazakhstan."].number == "3"


def test_docx_table_questions_have_cell_location(rfp_docx: Path) -> None:
    by_text = {q.text: q for q in extract_docx_questions(rfp_docx)}

    saml = by_text["Does the platform support SAML?"]
    assert (saml.number, saml.location.table_row, saml.location.table_col) == ("1", 1, 1)


def test_docx_long_paragraph_yields_only_the_question_sentence(rfp_docx: Path) -> None:
    texts = [q.text for q in extract_docx_questions(rfp_docx)]

    assert factories.LONG_QUESTION in texts
    assert not any("committee" in text for text in texts)


def test_docx_extraction_meets_95_percent_with_no_noise(rfp_docx: Path) -> None:
    texts = [q.text for q in extract_docx_questions(rfp_docx)]

    found = [item for item in factories.RFP_EXPECTED if any(item in text for text in texts)]
    recall = len(found) / len(factories.RFP_EXPECTED)
    noise = [item for item in factories.RFP_NOISE if any(item in text for text in texts)]

    print(f"\nquestion recall on test RFP: {recall:.1%} ({len(found)}/{len(factories.RFP_EXPECTED)})")
    assert recall >= 0.95
    assert noise == []
    assert len(texts) == len(factories.RFP_EXPECTED)


def test_pdf_questions_have_page_and_line(tmp_path: Path) -> None:
    path = factories.build_pdf(
        tmp_path / "rfp.pdf",
        [
            [
                "Questionnaire",
                "1. Describe your backup policy.",
                "2. Do you encrypt data",
                "at rest and in transit?",
            ],
            ["Company founded in 2012.", "3. Provide the SLA uptime."],
        ],
    )

    questions = extract_pdf_questions(path)

    assert [(q.number, q.location.page, q.location.line) for q in questions] == [
        ("1", 1, 2),
        ("2", 1, 3),
        ("3", 2, 2),
    ]
    assert questions[1].text == "Do you encrypt data at rest and in transit?"


def make_question(qid: str, text: str, block: int) -> Question:
    return Question(qid=qid, text=text, location=Location(block=block))


def test_merge_edits_updates_removes_and_adds_in_document_order() -> None:
    extracted = [
        make_question("q1", "one?", 1),
        make_question("q2", "two?", 3),
        make_question("q3", "three?", 5),
    ]
    edits = QuestionEdits(
        updated={"q1": "one, fixed?"},
        removed={"q2"},
        added=[make_question("m1", "missed?", 4)],
    )

    merged = merge_edits(extracted, edits)

    assert [(q.qid, q.text) for q in merged] == [("q1", "one, fixed?"), ("m1", "missed?"), ("q3", "three?")]
    assert extracted[0].text == "one?"  # input list is not mutated
