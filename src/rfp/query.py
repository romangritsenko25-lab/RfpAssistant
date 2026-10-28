"""Cross-language query expansion: the same question in every language the knowledge base uses."""

import json
import logging
import re
from functools import lru_cache

from rfp.config import get_settings
from rfp.llm import ChatClient, LLMUsage, OpenAIChatClient

logger = logging.getLogger(__name__)

LANGUAGES = ("ru", "kk", "en")

TRANSLATE_PROMPT = """You translate search queries for a multilingual knowledge base (ru, kk, en).
Given a question, return one JSON object with the keys "ru", "kk" and "en": the question rendered in each
language. Keep numbers, names, abbreviations and standard identifiers unchanged. Prefer the terms a
corporate policy or contract would use. Do not answer the question and do not add anything else."""


class QueryTranslator:
    """Translates a question into ru/kk/en with one cheap model call; failures give no variants."""

    def __init__(self, llm: ChatClient) -> None:
        self._llm = llm
        self.usage: list[LLMUsage] = []

    def variants(self, question: str) -> list[str]:
        """Translations of ``question`` that differ from it; empty when the call or its reply fails."""
        try:
            reply = self._llm.complete_json(TRANSLATE_PROMPT, question)
            self.usage.append(reply.usage)

            data = json.loads(reply.content)
        except Exception as error:  # search must still work on the original question
            logger.warning(
                "Query translation failed (%s); searching the original question only", type(error).__name__
            )
            return []
        if not isinstance(data, dict):
            return []
        seen = {_key(question)}
        found: list[str] = []
        for language in LANGUAGES:
            value = data.get(language)
            if isinstance(value, str) and value.strip() and _key(value) not in seen:
                seen.add(_key(value))
                found.append(value.strip())
        return found


def _key(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


@lru_cache
def default_translator() -> QueryTranslator | None:
    """The translator built from settings, or None when translation is off or there is no API key."""
    settings = get_settings()
    if not settings.query_translation or settings.llm_api_key is None:
        return None
    return QueryTranslator(OpenAIChatClient(settings, model=settings.query_model or settings.llm_model))
