"""Central configuration. Relocatable: sqlite + ./output defaults, no absolute paths."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal


from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore",
    )

    app_name: str = "ZozaFactory"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8001

    database_url: str = "sqlite:///./factory.db"
    output_dir: str = "./output"

    reality_min_trust: float = 0.6
    shared_bus_forwarding: bool = False

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
