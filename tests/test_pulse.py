"""Pulse agent tests (scraper faked)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from agents.pulse import agent as pulse
from agents.trend_scout import scraper
from agents.trend_scout.scraper import ScrapedProduct
from core import db
from core.config import get_settings
from core.models import AgentLedger, PriceSnapshot, Product


@pytest.fixture()
def isolated(tmp_path, monkeypatch) -> Iterator:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield tmp_path
    db.reset_engine()
    get_settings.cache_clear()


def _p(item_id: int, title: str, sold: int) -> ScrapedProduct:
    return ScrapedProduct(item_id, 10, title, f"https://x/i.10.{item_id}", 3000, sold, None)


class TestDetectSpikes:
    def test_new_product_is_spike(self) -> None:
        spikes = pulse.detect_spikes([_p(1, "nova", 100)], {})
        assert spikes == [{"item_id": 1, "title": "nova", "kind": "new",
                           "sold": 100, "jump": None}]

    def test_big_jump_is_spike(self) -> None:
        prev = {1: PriceSnapshot(product_id=1, captured_at=datetime.now(UTC),
                                 price_cents=3000, sold_count=100, run_id="r")}
        spikes = pulse.detect_spikes([_p(1, "subiu", 700)], prev)
        assert spikes[0]["kind"] == "jump"
        assert spikes[0]["jump"] == 600

    def test_small_delta_not_spike(self) -> None:
        prev = {1: PriceSnapshot(product_id=1, captured_at=datetime.now(UTC),
                                 price_cents=3000, sold_count=100, run_id="r")}
        assert pulse.detect_spikes([_p(1, "estavel", 400)], prev) == []


def _patch_scrape(monkeypatch, products: list[ScrapedProduct]) -> None:
    monkeypatch.setattr(
        scraper, "scrape_best_sellers", lambda *a, **k: products
    )


def test_plain_products_never_spike(isolated, monkeypatch) -> None:
    _patch_scrape(monkeypatch, [
        _p(1, "Camiseta Basica Lisa Algodao", 5000),
        _p(2, "Camiseta Estampada Anime", 100),
    ])
    out = pulse.run_once()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["spikes"]) == 1
    assert payload["spikes"][0]["item_id"] == 2


def test_first_run_marks_everything_new(isolated, monkeypatch) -> None:
    _patch_scrape(monkeypatch, [_p(1, "a", 100), _p(2, "b", 200)])
    out = pulse.run_once(max_products=20)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["product_count"] == 2
    assert len(payload["spikes"]) == 2
    assert all(sp["kind"] == "new" for sp in payload["spikes"])

    with db.session_scope() as s:
        runs = list(s.exec(select(AgentLedger).where(AgentLedger.agent == "pulse")).all())
    assert len(runs) == 1 and runs[0].status == "success"


def test_second_run_detects_jump(isolated, monkeypatch) -> None:
    _patch_scrape(monkeypatch, [_p(1, "a", 100)])
    pulse.run_once()

    # backdate the snapshot so the next run sees it as "previous"
    with db.session_scope() as s:
        for snap in s.exec(select(PriceSnapshot)).all():
            snap.captured_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
            s.add(snap)
        s.commit()

    _patch_scrape(monkeypatch, [_p(1, "a", 900)])
    out = pulse.run_once()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["spikes"]) == 1
    assert payload["spikes"][0]["kind"] == "jump"
    assert payload["spikes"][0]["jump"] == 800

    with db.session_scope() as s:
        products = list(s.exec(select(Product)).all())
    assert len(products) == 1  # upserted, not duplicated
