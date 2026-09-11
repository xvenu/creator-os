"""MusicPulse core configuration."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MusicPulse"
    environment: str = "development"
    secret_key: str = "change-me"
    database_url: str = "sqlite:///./musicpulse.db"
    redis_url: str = "redis://localhost:6379/0"
    telegram_bot_token: str = ""
    telegram_admin_ids: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    youtube_api_key: str = ""
    tiktok_session_id: str = ""
    hf_model: str = "microsoft/Phi-3-mini-4k-instruct"
    # --- Phase 2 ---
    markets: str = "US,CA,UK,AU,DE"
    default_country: str = "US"
    default_timezone: str = "ET"
    revenue_currency: str = "USD"
    mrr_target: float = 10000.0
    # --- Phase 3: autonomy ---
    autonomy_enabled: bool = True
    autonomy_max_posts_per_cycle: int = 3
    autonomy_default_horizon: str = "daily"
    # --- Phase 4: growth network ---
    growth_target_followers_per_day: int = 100
    default_cpa_cap: float = 1.50
    forecast_horizons: str = "7,30,90"
    # --- Phase 6: Zoza Video Factory + Creator-OS ---
    zoza_webhook_url: str = ""
    zoza_api_key: str = ""
    zoza_factory_name: str = "zoza-video-factory"
    pipeline_enabled: bool = True
    pipeline_min_priority: float = 50.0
    # --- Phase 7: reality-first ---
    reality_min_trust: float = 0.6
    reality_require_verification: bool = True
    # --- Phase 8: responsibility refactor ---
    telegram_enabled: bool = True  # deprecated: Creator-OS owns Telegram
    creator_webhook_url: str = ""
    factory_name: str = "zoza-video-factory"

    @property
    def market_list(self) -> list[str]:
        return [c.strip().upper() for c in self.markets.split(",") if c.strip()]

    @property
    def admin_ids(self) -> list[int]:
        if not self.telegram_admin_ids.strip():
            return []
        return [int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
