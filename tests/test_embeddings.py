from types import SimpleNamespace

import pytest

from rfp.config import Settings
from rfp.embeddings import BATCH_SIZE, OpenAIEmbedder, get_embedder


class StubClient:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.batches: list[list[str]] = []
        self.embeddings = SimpleNamespace(create=self.create)

    def create(self, model: str, input: list[str]) -> SimpleNamespace:
        self.batches.append(input)
        data = [SimpleNamespace(index=i, embedding=[float(len(t))] * self.dim) for i, t in enumerate(input)]
        # Reversed to prove that the embedder restores the input order.
        return SimpleNamespace(data=list(reversed(data)))


def make_embedder(dim: int = 3, client_dim: int = 3) -> tuple[OpenAIEmbedder, StubClient]:
    embedder = OpenAIEmbedder("http://localhost/v1", "key", "model", dim)
    client = StubClient(client_dim)
    embedder._client = client  # type: ignore[assignment]
    return embedder, client


def test_embed_batches_and_keeps_order():
    embedder, client = make_embedder()
    texts = ["x" * n for n in range(1, BATCH_SIZE + 6)]
    vectors = embedder.embed(texts)
    assert [len(b) for b in client.batches] == [BATCH_SIZE, 5]
    assert [v[0] for v in vectors] == [float(len(t)) for t in texts]


def test_embed_empty_makes_no_request():
    embedder, client = make_embedder()
    assert embedder.embed([]) == []
    assert client.batches == []


def test_wrong_dimension_is_an_error():
    embedder, _ = make_embedder(dim=3, client_dim=5)
    with pytest.raises(ValueError, match="EMBEDDING_DIM=3"):
        embedder.embed(["text"])


def test_get_embedder_uses_settings():
    settings = Settings(_env_file=None, database_url="postgresql://x", embedding_dim=8)  # type: ignore[call-arg]
    embedder = get_embedder(settings)
    assert isinstance(embedder, OpenAIEmbedder)
    assert embedder.dim == 8
