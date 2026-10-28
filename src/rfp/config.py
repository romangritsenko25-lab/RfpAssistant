"""Application settings, read from environment variables and an optional ``.env`` file."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    database_url: str
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY")
    )
    llm_model: str = "gpt-4o-mini"
    judge_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = Field(default=1536, gt=0)
    kb_dir: Path = Path("data/kb")
    poll_interval_s: int = Field(default=60, ge=1, le=300)
    retrieval_top_k: int = Field(default=8, ge=1)
    query_translation: bool = True  # search also the question translated to ru/kk/en
    query_model: str | None = None  # model for the translation call; defaults to llm_model
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    answer_prompt_path: Path = Path("prompts/answer.md")
    judge_prompt_path: Path = Path("prompts/judge.md")
    # Web access. Without SECRET_KEY a random key is generated per process: sessions do not survive a restart.
    secret_key: SecretStr | None = None
    cookie_secure: bool = False  # set true when the service is served over HTTPS
    admin_username: str | None = None
    admin_password: SecretStr | None = None
    watch_kb: bool = True  # poll KB_DIR in a background thread
    job_workers: int = Field(default=2, ge=1)
    max_upload_mb: int = Field(default=25, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
