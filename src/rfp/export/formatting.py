from rfp.models import Answer


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
