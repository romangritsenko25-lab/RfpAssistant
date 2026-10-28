from types import SimpleNamespace

import httpx
import openai
import pytest

from rfp.config import Settings
from rfp.llm import OpenAIChatClient, estimate_cost


def make_settings(model: str = "gpt-4o-mini") -> Settings:
    return Settings(database_url="postgresql://unused", llm_model=model, _env_file=None)


def completion(content: str = '{"ok": true}') -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=1000, completion_tokens=200),
    )


class FakeCompletions:
    def __init__(self, results: list) -> None:
        self.results = results
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def fake_openai(results: list) -> tuple[SimpleNamespace, FakeCompletions]:
    completions = FakeCompletions(results)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def bad_request() -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "http://localhost/v1/chat/completions"))
    return openai.BadRequestError("response_format is not supported", response=response, body=None)


def test_estimate_cost_uses_price_table() -> None:
    assert estimate_cost("gpt-4o-mini", 1_000_000, 1_000_000) == pytest.approx(0.75)


def test_estimate_cost_unknown_model_is_none() -> None:
    assert estimate_cost("my-local-model", 1000, 1000) is None


def test_complete_json_returns_content_and_usage() -> None:
    fake, completions = fake_openai([completion()])
    reply = OpenAIChatClient(make_settings(), client=fake).complete_json("system", "user")

    assert reply.content == '{"ok": true}'
    assert reply.usage.prompt_tokens == 1000
    assert reply.usage.completion_tokens == 200
    assert reply.usage.cost_usd == pytest.approx(0.00027)
    assert reply.usage.latency_s >= 0
    assert completions.calls[0]["response_format"] == {"type": "json_object"}
    assert completions.calls[0]["messages"][0] == {"role": "system", "content": "system"}


def test_falls_back_without_response_format_and_remembers_it() -> None:
    fake, completions = fake_openai([bad_request(), completion(), completion()])
    client = OpenAIChatClient(make_settings(), client=fake)

    client.complete_json("s", "u")
    client.complete_json("s", "u")

    assert "response_format" in completions.calls[0]
    assert "response_format" not in completions.calls[1]
    assert "response_format" not in completions.calls[2]


def test_missing_usage_and_unknown_model() -> None:
    reply_obj = completion()
    reply_obj.usage = None
    fake, _ = fake_openai([reply_obj])
    reply = OpenAIChatClient(make_settings("local-model"), client=fake).complete_json("s", "u")

    assert reply.usage.prompt_tokens == 0
    assert reply.usage.cost_usd is None


def test_model_override_is_used_for_the_request() -> None:
    fake, completions = fake_openai([completion()])
    settings = make_settings("gpt-4o-mini")

    reply = OpenAIChatClient(settings, client=fake, model="gpt-4o").complete_json("s", "u")

    assert completions.calls[0]["model"] == "gpt-4o"
    assert reply.usage.model == "gpt-4o"
    assert reply.usage.cost_usd == pytest.approx(0.0045)
