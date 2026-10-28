import json

from rfp.llm import LLMReply, LLMUsage
from rfp.query import QueryTranslator


class FakeLLM:
    def __init__(self, content: str | Exception) -> None:
        self._content = content

    def complete_json(self, system: str, user: str) -> LLMReply:
        if isinstance(self._content, Exception):
            raise self._content
        return LLMReply(content=self._content, usage=LLMUsage(model="fake"))


def test_variants_exclude_the_original_and_duplicates():
    reply = json.dumps(
        {"ru": "Как часто бэкап?", "kk": "Сақтық көшірме қаншалықты жиі?", "en": "How often is backup?"}
    )
    translator = QueryTranslator(FakeLLM(reply))
    assert translator.variants("How often is backup?") == [
        "Как часто бэкап?",
        "Сақтық көшірме қаншалықты жиі?",
    ]
    assert len(translator.usage) == 1


def test_variants_ignore_bad_values():
    translator = QueryTranslator(FakeLLM(json.dumps({"ru": 5, "kk": "  ", "en": "Backup?"})))
    assert translator.variants("Резервное копирование?") == ["Backup?"]


def test_variants_survive_failures():
    assert QueryTranslator(FakeLLM(RuntimeError("network"))).variants("q") == []
    assert QueryTranslator(FakeLLM("not json")).variants("q") == []
    assert QueryTranslator(FakeLLM("[1, 2]")).variants("q") == []


def test_failure_is_logged_without_question_text(caplog):
    with caplog.at_level("WARNING", logger="rfp.query"):
        QueryTranslator(FakeLLM(RuntimeError("secret detail"))).variants("confidential question")
    assert "RuntimeError" in caplog.text
    assert "confidential question" not in caplog.text
    assert "secret detail" not in caplog.text
