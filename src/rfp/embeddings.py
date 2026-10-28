"""Text embeddings through an OpenAI-compatible API."""

from typing import Protocol

from openai import OpenAI

from rfp.config import Settings, get_settings

BATCH_SIZE = 64


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """Embeds texts in batches; checks that the vectors have the configured size."""

    def __init__(self, base_url: str, api_key: str | None, model: str, dim: int) -> None:
        self.dim = dim
        self._model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key or "missing-api-key")

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            response = self._client.embeddings.create(model=self._model, input=batch)
            for item in sorted(response.data, key=lambda d: d.index):
                if len(item.embedding) != self.dim:
                    raise ValueError(
                        f"Model {self._model} returned {len(item.embedding)}-dimensional vectors, "
                        f"expected EMBEDDING_DIM={self.dim}"
                    )
                vectors.append(item.embedding)
        return vectors


def get_embedder(settings: Settings | None = None) -> Embedder:
    settings = settings or get_settings()
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return OpenAIEmbedder(settings.llm_base_url, api_key, settings.embedding_model, settings.embedding_dim)
