"""Central configuration with environment-based overrides and secrets support."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FootballPulse V2"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = Field(
        default="postgresql+asyncpg://football:football@localhost:5432/footballpulse",
        description="Async SQLAlchemy database URL",
    )
    database_pool_size: int = 10
    database_max_overflow: int = 10
    database_echo: bool = False

    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    redis_queue_prefix: str = "fp:queue"
    redis_default_ttl_seconds: int = 86400

    # Retry defaults
    retry_max_attempts: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 30.0

    # Agent defaults
    agent_default_timeout_seconds: float = 120.0
    agent_heartbeat_interval_seconds: int = 30

    # Secrets are expected via environment / secret manager, never committed.
    # e.g. YOUTUBE_API_KEY, OPENAI_API_KEY, etc. — accessed via SecretsManager.

    @field_validator("database_url")
    @classmethod
    def _validate_db(cls, v: str) -> str:
        if "://" not in v:
            raise ValueError("database_url must be a valid URL")
        return v

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def sync_database_url(self) -> str:
        """Convert async URL to sync (psycopg2) for Alembic."""
        return self.database_url.replace("+asyncpg", "")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
