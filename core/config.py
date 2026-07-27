"""App configuration (pydantic-settings, reads .env at project root)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (local Ollama only)
    llm_model: str = "qwen2.5:14b-instruct"
    llm_host: str = "http://localhost:11434"

    # Scraper
    scrape_max_products: int = 500
    scrape_category_url: str = ""
    scrape_delay_min_sec: float = 3.0
    scrape_delay_max_sec: float = 6.0
    scrape_headless: bool = True

    # Scheduler (weekly)
    schedule_cron_weekday: str = "mon"
    schedule_cron_hour: int = 9

    # Storage
    db_path: Path = PROJECT_ROOT / "data" / "shopee.db"
    ledger_path: Path = PROJECT_ROOT / "data" / "ledger.jsonl"

    @property
    def data_dir(self) -> Path:
        return self.db_path.parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
