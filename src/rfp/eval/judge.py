"""LLM judge: compares a candidate answer with the expert reference."""

from typing import get_args

from rfp.answering import parse_model_json
from rfp.eval.metrics import GoldItem, Verdict
from rfp.llm import ChatClient, LLMUsage

_VERDICTS = set(get_args(Verdict)) - {"unjudged"}


def build_judge_message(item: GoldItem, candidate: str) -> str:
    return (
        f"Question:\n{item.question}\n\n"
        f"Reference answer:\n{item.gold_answer}\n\n"
        f"Candidate answer:\n{candidate}"
    )


def judge_answer(
    client: ChatClient, system_prompt: str, item: GoldItem, candidate: str
) -> tuple[Verdict, str, LLMUsage]:
    """Return ``(verdict, reason, usage)``; a reply without a valid verdict gives ``unjudged``."""
    reply = client.complete_json(system_prompt, build_judge_message(item, candidate))
    data = parse_model_json(reply.content)
    verdict = data.get("verdict") if data else None
    if verdict not in _VERDICTS:
        return "unjudged", "judge reply was not valid", reply.usage
    reason = data.get("reason", "") if data else ""
    return verdict, reason if isinstance(reason, str) else "", reply.usage
