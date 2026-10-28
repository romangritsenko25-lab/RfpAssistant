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
    retrieval_top_k: int = Field(default=5, ge=1)
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    answer_prompt_path: Path = Path("prompts/answer.md")
    judge_prompt_path: Path = Path("prompts/judge.md")


@lru_cache
def get_settings() -> Settings:
    return Settings()
