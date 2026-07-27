"""Trend Scout agent orchestration tests (scraper + LLM faked)."""

import json
from collections.abc import Iterator

import pytest
from sqlmodel import select

from agents.trend_scout import agent, scraper
from agents.trend_scout.scraper import ScrapedProduct
from core import db
from core.config import get_settings
from core.models import AgentLedger, PriceSnapshot, Product


@pytest.fixture()
def isolated(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))  # not a real env var; kept for clarity
    get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield tmp_path
    db.reset_engine()
    get_settings.cache_clear()


def _fake_products() -> list[ScrapedProduct]:
    return [
        ScrapedProduct(1, 10, "camiseta meme gato", "https://x/i.10.1", 3000, 500, 4.8),
        ScrapedProduct(2, 10, "camiseta basica lisa", "https://x/i.10.2", 2000, 900, None),
    ]


class FakeLLM:
    def chat(self, model, messages, **kwargs):
        return {"message": {"content": json.dumps({"clusters": []})}}


def _patch_scraper(monkeypatch, calls: list) -> None:
    def fake(max_products=None, *, dry_run=False, **kwargs):
        calls.append({"max_products": max_products, "dry_run": dry_run})
        return _fake_products()

    monkeypatch.setattr(scraper, "scrape_best_sellers", fake)


def test_run_once_persists_and_reports(isolated, tmp_path, monkeypatch) -> None:
    calls: list = []
    _patch_scraper(monkeypatch, calls)

    out_dir = agent.run_once(dry_run=True, client=FakeLLM())

    assert out_dir is not None and (out_dir / "report.md").exists()
    assert (out_dir / "prices.png").exists()
    assert len(calls) == 1

    with db.session_scope() as s:
        products = list(s.exec(select(Product)).all())
        snapshots = list(s.exec(select(PriceSnapshot)).all())
        runs = list(s.exec(select(AgentLedger)).all())

    assert {p.item_id for p in products} == {1, 2}
    assert len(snapshots) == 2
    assert {snap.price_cents for snap in snapshots} == {3000, 2000}
    assert len(runs) == 1 and runs[0].status == "success"
    assert runs[0].outputs_path == str(out_dir)


def test_run_once_idempotent_skip(isolated, monkeypatch) -> None:
    calls: list = []
    _patch_scraper(monkeypatch, calls)

    first = agent.run_once(dry_run=True, client=FakeLLM())
    second = agent.run_once(dry_run=True, client=FakeLLM())

    assert len(calls) == 1  # second run skipped
    assert second == first


def test_run_once_force_bypasses_idempotency(isolated, monkeypatch) -> None:
    calls: list = []
    _patch_scraper(monkeypatch, calls)

    agent.run_once(dry_run=True, client=FakeLLM())
    agent.run_once(dry_run=True, client=FakeLLM(), force=True)

    assert len(calls) == 2


def test_failed_scrape_marks_ledger_error(isolated, monkeypatch) -> None:
    def boom(**kwargs):
        raise RuntimeError("shopee down")

    monkeypatch.setattr(scraper, "scrape_best_sellers", boom)

    with pytest.raises(RuntimeError, match="shopee down"):
        agent.run_once(dry_run=True, client=FakeLLM())

    with db.session_scope() as s:
        runs = list(s.exec(select(AgentLedger)).all())
    assert len(runs) == 1
    assert runs[0].status == "error"
    assert "shopee down" in runs[0].error


def test_brl_formatting() -> None:
    assert agent._brl(123456) == "R$ 1.234,56"
    assert agent._brl(5000) == "R$ 50,00"
