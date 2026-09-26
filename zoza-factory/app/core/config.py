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

    # Render provider selection (Pulse never sees this): local-ffmpeg is the
    # default production path; "simulated" is an explicitly named test-only
    # provider; "runpod" selects the GPU provider (requires RUNPOD_* below).
    render_provider: str = "local-ffmpeg"
    render_fps: int = 24

    # RunPod GPU provider (real integration; unset = unavailable, fail-closed
    # with an explicit error — never silently fall back and claim GPU work).
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""
    runpod_timeout_seconds: float = 600.0

    # Production storage: local filesystem default; s3-compatible optional.
    storage_backend: str = "local"
    storage_s3_bucket: str = ""
    storage_s3_prefix: str = "zoza-exports/"
    storage_s3_endpoint: str = ""

    # Factory auth: per-pulse bearer tokens + admin token. Empty = auth
    # disabled (development only); production requires all three set.
    pulse_token_music: str = ""
    pulse_token_football: str = ""
    factory_admin_token: str = ""

    @property
    def is_test(self) -> bool:
        return self.environment == "test"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
