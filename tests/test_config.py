"""Settings defaults + env-override behavior."""

from __future__ import annotations

import pytest

from core.config import PROJECT_ROOT, get_settings


def test_defaults() -> None:
    get_settings.cache_clear()
    s = get_settings()
    assert s.shopee_auth_path == PROJECT_ROOT / "data" / "shopee_auth.json"
    assert s.llm_model == "qwen2.5:14b-instruct"
    assert s.scrape_keyword == "camiseta estampada"
    assert s.scrape_max_products == 640
    assert s.scrape_max_per_keyword == 80
    assert s.scrape_keywords == [
        "camiseta streetwear",
        "camiseta oversized estampada",
        "camiseta anime geek",
        "camiseta gospel cristã",
        "camiseta country agro",
        "camiseta rock vintage",
        "camiseta gym academia",
        "camiseta automotiva moto",
    ]
    assert s.schedule_cron_weekday == "mon"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCRAPE_MAX_PRODUCTS", "10")
    get_settings.cache_clear()
    assert get_settings().scrape_max_products == 10


def test_class_field_defaults() -> None:
    from core.config import Settings

    s = Settings(_env_file=None)
    assert s.scrape_max_products == 640
    assert s.scrape_max_per_keyword == 80
