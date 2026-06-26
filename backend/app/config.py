from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    api_host: str = Field(default="127.0.0.1", validation_alias="API_HOST")
    api_port: int = Field(default=8001, validation_alias="API_PORT")

    # Phase 8 — Perplexity Sonar (optional; regex remains default until EXTRACTION_USE_LLM=true)
    perplexity_api_key: str | None = Field(default=None, validation_alias="PERPLEXITY_API_KEY")
    perplexity_model: str = Field(default="sonar", validation_alias="PERPLEXITY_MODEL")
    extraction_use_llm: bool = Field(default=False, validation_alias="EXTRACTION_USE_LLM")


settings = Settings()
