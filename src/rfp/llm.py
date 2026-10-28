"""Thin client for OpenAI-compatible chat APIs that return a JSON object."""

import time
from typing import Protocol

import openai
from pydantic import BaseModel

from rfp.config import Settings

# USD per 1M tokens as (input, output). Reference values only: provider prices change,
# verify them against the provider's price list before quoting any cost figure.
PRICES_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
}


class LLMUsage(BaseModel):
    """What one model call cost; ``cost_usd`` is None when the model has no entry in the price table."""

    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float | None = None
    latency_s: float = 0.0


class LLMReply(BaseModel):
    content: str
    usage: LLMUsage


class ChatClient(Protocol):
    """Anything that can answer a system+user prompt with JSON text; tests substitute a fake."""

    def complete_json(self, system: str, user: str) -> LLMReply: ...


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Cost in USD from :data:`PRICES_USD_PER_1M`, or None for a model without a known price."""
    price = PRICES_USD_PER_1M.get(model)
    if price is None:
        return None
    return (prompt_tokens * price[0] + completion_tokens * price[1]) / 1_000_000


class OpenAIChatClient:
    """Chat client for OpenAI and compatible servers (Ollama, vLLM) configured through Settings."""

    def __init__(
        self, settings: Settings, client: openai.OpenAI | None = None, model: str | None = None
    ) -> None:
        self._model = model or settings.llm_model
        api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
        # Local servers ignore the key, but the SDK refuses an empty one.
        self._client = client or openai.OpenAI(
            base_url=settings.llm_base_url, api_key=api_key or "not-needed", max_retries=2
        )
        self._json_mode = True

    def complete_json(self, system: str, user: str) -> LLMReply:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        started = time.perf_counter()
        response = self._create(messages)
        latency = time.perf_counter() - started
        usage = response.usage
        prompt_tokens = usage.prompt_tokens if usage else 0
        completion_tokens = usage.completion_tokens if usage else 0
        content = response.choices[0].message.content or ""
        return LLMReply(
            content=content,
            usage=LLMUsage(
                model=self._model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=estimate_cost(self._model, prompt_tokens, completion_tokens),
                latency_s=latency,
            ),
        )

    def _create(self, messages: list[dict[str, str]]):
        if self._json_mode:
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=0,
                    response_format={"type": "json_object"},
                )
            except openai.BadRequestError:
                # Some local servers do not support response_format; the prompts ask for JSON anyway.
                self._json_mode = False
        return self._client.chat.completions.create(model=self._model, messages=messages, temperature=0)
