"""App configuration (pydantic-settings, reads .env at project root)."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM Settings
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model_pool: str | list[str] = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]
    gemini_max_retries_503: int = 5
    gemini_retry_delay_sec: float = 4.0

    # LLM (local Ollama only)
    llm_model: str = "qwen2.5:14b-instruct"
    llm_host: str = "http://localhost:11434"

    # Scraper
    scrape_max_products: int = 500
    scrape_keyword: str = "camiseta estampada"
    scrape_keywords: list[str] = [
        "camiseta estampada",
        "camiseta streetwear",
        "camiseta anime",
        "camiseta gospel",
        "camiseta vintage",
    ]
    scrape_category_url: str = ""
    scrape_delay_min_sec: float = 3.0
    scrape_delay_max_sec: float = 6.0
    scrape_headless: bool = True

    # Scheduler (weekly deep run + daily pulse)
    schedule_cron_weekday: str = "mon"
    schedule_cron_hour: int = 9
    schedule_pulse_hour: int = 8

    # Storage
    db_path: Path = PROJECT_ROOT / "data" / "shopee.db"
    ledger_path: Path = PROJECT_ROOT / "data" / "ledger.jsonl"
    shopee_auth_path: Path = PROJECT_ROOT / "data" / "shopee_auth.json"

    # Outreach CRM Identity
    sender_name: str = "Trend Scout BR"
    sender_email: str = "contato.trendscout@gmail.com"
    sender_instagram: str = "trendscoutbr"

    # Web Portal (Vercel)
    portal_url: str = "https://trendscout-shopee.vercel.app"
    portal_display_url: str = "trendscout-shopee.vercel.app"


    @field_validator("gemini_model_pool", mode="before")
    @classmethod
    def parse_model_pool(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v

    @field_validator("db_path", "ledger_path", "shopee_auth_path", mode="after")
    @classmethod
    def resolve_paths(cls, v: Path) -> Path:
        """Resolve relative storage paths against PROJECT_ROOT."""
        if not v.is_absolute():
            return PROJECT_ROOT / v
        return v

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
