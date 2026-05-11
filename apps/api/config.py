"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Vibe Coder", alias="APP_NAME")
    app_url: str = Field(default="http://localhost:8000", alias="APP_URL")
    database_url: str = Field(default="sqlite:///./runtime/vibecoder.db", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    default_model: str = Field(
        default="anthropic/claude-3.7-sonnet",
        alias="DEFAULT_MODEL",
    )
    default_max_iterations: int = Field(default=3, alias="DEFAULT_MAX_ITERATIONS")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    web_origin: str = Field(default="http://localhost:5173", alias="WEB_ORIGIN")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    sandbox_default_image: str = Field(default="python:3.12-slim", alias="SANDBOX_DEFAULT_IMAGE")
    sandbox_node_image: str = Field(default="node:20-bookworm-slim", alias="SANDBOX_NODE_IMAGE")
    sandbox_timeout_seconds: int = Field(default=900, alias="SANDBOX_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def runtime_dir(self) -> Path:
        return Path("runtime")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    return settings

