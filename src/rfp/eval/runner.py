"""Run questions through retrieval, answering and the judge, producing :class:`EvalRecord` rows."""

import time
from collections.abc import Callable

from rfp.answering import answer_question
from rfp.config import Settings
from rfp.eval.judge import judge_answer
from rfp.eval.metrics import EvalRecord, GoldItem
from rfp.llm import ChatClient
from rfp.models import Location, Question, RetrievedChunk

Retriever = Callable[[str], list[RetrievedChunk]]


def run_items(
    items: list[GoldItem],
    retrieve: Retriever,
    answer_llm: ChatClient,
    judge_llm: ChatClient,
    settings: Settings,
    judge_prompt: str,
) -> list[EvalRecord]:
    """Answer each gold question and judge the answers to answerable ones.

    Timing and answer cost cover retrieval and generation; judge usage is separate. The gold question text
    is used as is, so answer quality is measured apart from question extraction (reported separately).
    """
    return [_run_one(item, retrieve, answer_llm, judge_llm, settings, judge_prompt) for item in items]


def _run_one(
    item: GoldItem,
    retrieve: Retriever,
    answer_llm: ChatClient,
    judge_llm: ChatClient,
    settings: Settings,
    judge_prompt: str,
) -> EvalRecord:
    started = time.perf_counter()
    chunks = retrieve(item.question)
    generated = answer_question(
        Question(qid=item.id, text=item.question, location=Location()), chunks, answer_llm, settings
    )
    seconds = time.perf_counter() - started

    answer = generated.answer
    usage = generated.usage
    record = EvalRecord(
        item=item,
        answer=answer,
        retrieved_doc_ids=[chunk.doc_id for chunk in chunks],
        seconds=seconds,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        cost_usd=(usage.cost_usd if usage else 0.0),
        rejected_citations=generated.rejected_citations,
    )
    if item.answerable:
        if answer.status == "no_data":
            record.verdict, record.verdict_reason = "incorrect", "refused with no_data"
        else:
            record.verdict, record.verdict_reason, judge_usage = judge_answer(
                judge_llm, judge_prompt, item, answer.text
            )
            record.judge_prompt_tokens = judge_usage.prompt_tokens
            record.judge_completion_tokens = judge_usage.completion_tokens
            record.judge_cost_usd = judge_usage.cost_usd
    return record
