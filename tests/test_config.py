import pytest
from pydantic import ValidationError

from rfp.config import Settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_API_KEY", "OPENAI_API_KEY", "POLL_INTERVAL_S", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)


def test_defaults_and_required_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u@localhost/db")

    settings = Settings(_env_file=None)

    assert settings.poll_interval_s == 60
    assert settings.llm_api_key is None
    assert settings.embedding_dim == 1536


def test_missing_database_url_fails() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_api_key_falls_back_to_openai_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "from-openai")

    settings = Settings(_env_file=None)

    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "from-openai"
    assert "from-openai" not in repr(settings)


def test_llm_api_key_wins_over_openai_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "from-openai")
    monkeypatch.setenv("LLM_API_KEY", "from-llm")

    assert Settings(_env_file=None).llm_api_key.get_secret_value() == "from-llm"


def test_poll_interval_above_five_minutes_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "x")
    monkeypatch.setenv("POLL_INTERVAL_S", "301")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_empty_values_from_env_example_use_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "x")
    monkeypatch.setenv("POLL_INTERVAL_S", "")

    assert Settings(_env_file=None).poll_interval_s == 60
