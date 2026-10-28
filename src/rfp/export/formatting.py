from rfp.documents.language import detect_language
from rfp.models import Answer, Question

NO_DATA_LABEL = {
    "ru": "Нет данных в базе знаний",
    "kk": "Білім базасында дерек жоқ",
    "en": "No data in the knowledge base",
}


def sources_line(answer: Answer) -> str:
    """One-line list of cited documents and sections, empty when there are no citations."""
    if not answer.citations:
        return ""
    cited = "; ".join(f"{c.doc_id}, {c.section}" for c in answer.citations)
    return f"Sources: {cited}"


def answer_with_sources(answer: Answer) -> str:
    """Answer text followed by its sources on a new line, for single-cell output."""
    sources = sources_line(answer)
    return f"{answer.text}\n{sources}" if sources else answer.text


def no_data_label(question: Question) -> str:
    """The fixed 'no data' note, in the language of the question."""
    return NO_DATA_LABEL[detect_language(question.text)]


def exported_text(question: Question, answer: Answer) -> str:
    """Exactly what is written for this answer: the fixed note when the knowledge base had no data."""
    if answer.status == "no_data":
        return no_data_label(question)
    return answer_with_sources(answer)
