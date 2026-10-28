import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from rfp.db import apply_schema, connect
from tests import factories


@pytest.fixture
def rfp_docx(tmp_path: Path) -> Path:
    return factories.build_rfp_docx(tmp_path / "rfp.docx")


@pytest.fixture
def questionnaire_xlsx(tmp_path: Path) -> Path:
    return factories.build_questionnaire_xlsx(tmp_path / "questionnaire.xlsx")


@pytest.fixture
def unicode_font() -> None:
    if factories.find_unicode_font() is None:
        pytest.skip("no TrueType font with Cyrillic glyphs on this machine")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "db: needs PostgreSQL with pgvector (TEST_DATABASE_URL)")


FAKE_DIM = 64


class FakeEmbedder:
    """Deterministic bag-of-words embedder: every word adds weight to one hashed dimension."""

    def __init__(self, dim: int = FAKE_DIM, overrides: dict[str, list[float]] | None = None) -> None:
        self.dim = dim
        self.calls = 0
        self._overrides = overrides or {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._overrides.get(text) or self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for word in re.findall(r"\w+", text.lower()):
            vector[int.from_bytes(hashlib.sha256(word.encode()).digest()[:4]) % self.dim] += 1.0
        norm = sum(x * x for x in vector) ** 0.5 or 1.0
        return [x / norm for x in vector]


@pytest.fixture
def fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture
def db_conn(test_database_url: str) -> Iterator[psycopg.Connection]:
    """A connection to the test database with freshly created tables."""
    conn = connect(test_database_url)
    conn.execute("DROP TABLE IF EXISTS chunks, documents CASCADE")
    apply_schema(conn, FAKE_DIM)
    yield conn
    conn.close()
