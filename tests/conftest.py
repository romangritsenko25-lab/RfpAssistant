import hashlib
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from rfp.app import create_app
from rfp.config import Settings
from rfp.db import apply_schema, connect
from rfp.llm import LLMReply, LLMUsage
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
    conn.execute(
        "DROP TABLE IF EXISTS llm_log, audit_log, reference_answers, job_items, jobs, users, "
        "chunks, documents CASCADE"
    )
    apply_schema(conn, FAKE_DIM)
    yield conn
    conn.close()


ADMIN_USER = "admin"
ADMIN_PASSWORD = "admin-pass-123"
KB_TEXT = "# Backup policy\n\n## Backups\n\nBackups of production databases are made every day at 02:00.\n"
BACKUP_QUOTE = "Backups of production databases are made every day"


class ScriptedLLM:
    """Chat client double: answers from the fragment for 'multi-factor', fails on 'сақтау', else no_data."""

    def __init__(self) -> None:
        self.calls = 0

    def complete_json(self, system: str, user: str):
        self.calls += 1
        if "сақтау" in user:
            raise RuntimeError("model unavailable")
        english = "Answer language: English" in user
        if "multi-factor" in user:
            body = {
                "text": "Backups run daily." if english else "Резервные копии делаются ежедневно.",
                "status": "answered",
                "confidence": 0.9,
                "citations": [{"fragment": 1, "quote": BACKUP_QUOTE}],
            }
        else:
            body = {
                "text": "No data." if english else "Нет данных.",
                "status": "no_data",
                "confidence": 0.9,
                "citations": [],
            }
        usage = LLMUsage(model="gpt-4o-mini", prompt_tokens=100, completion_tokens=20, cost_usd=0.001)
        return LLMReply(content=json.dumps(body), usage=usage)


@pytest.fixture
def api_settings(test_database_url: str, tmp_path: Path) -> Settings:
    prompt = tmp_path / "answer.md"
    prompt.write_text("SYSTEM PROMPT", encoding="utf-8")
    return Settings(
        database_url=test_database_url,
        embedding_dim=FAKE_DIM,
        kb_dir=tmp_path / "kb",
        answer_prompt_path=prompt,
        secret_key="test-secret-key",
        admin_username=ADMIN_USER,
        admin_password=ADMIN_PASSWORD,
        watch_kb=False,
        confidence_threshold=0.5,
        layout_mode="rules",
        _env_file=None,
    )


@pytest.fixture
def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM()


@pytest.fixture
def client(db_conn, api_settings, fake_embedder, scripted_llm):
    """A test client of the app on the test database; not logged in."""
    with TestClient(create_app(api_settings, embedder=fake_embedder, llm=scripted_llm)) as test_client:
        yield test_client


@pytest.fixture
def logged_in(client):
    response = client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
    assert response.status_code == 200
    return client


@pytest.fixture(autouse=True)
def no_query_translation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Tests never call the translation or layout model; tests of those pass a fake client explicitly."""
    from rfp.config import get_settings
    from rfp.query import default_translator

    monkeypatch.setenv("QUERY_TRANSLATION", "false")
    monkeypatch.setenv("LAYOUT_MODE", "rules")
    get_settings.cache_clear()
    default_translator.cache_clear()
    yield
    get_settings.cache_clear()
    default_translator.cache_clear()
