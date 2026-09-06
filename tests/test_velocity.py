import json
from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from agents.trend_scout.analyzer import analyze_trends
from agents.trend_scout.scraper import ScrapedProduct
from core.models import PriceSnapshot, Product
from tests.conftest import FakeLLM


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_velocity_metrics_via_analyze_trends(session: Session, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    now = datetime(2026, 1, 10, 12, 0, 0)

    # We need to mock datetime.now(UTC) in analyzer
    class MockDatetime:
        @classmethod
        def now(cls, tz=None):
            class _FakeDT:
                def replace(self, tzinfo=None):
                    return now

            return _FakeDT()

    import agents.trend_scout.analyzer

    monkeypatch.setattr(agents.trend_scout.analyzer, "datetime", MockDatetime)

    # Products in DB
    p1 = Product(
        id=1,
        item_id=1,
        shop_id=1,
        title="Camiseta P1",
        url="",
        first_seen_at=now - timedelta(days=20),
        last_seen_at=now,
    )
    c1 = PriceSnapshot(
        product_id=1, captured_at=now, price_cents=100, sold_count=100, run_id="curr"
    )
    pr1 = PriceSnapshot(
        product_id=1,
        captured_at=now - timedelta(days=10),
        price_cents=100,
        sold_count=50,
        run_id="prev",
    )

    p2 = Product(
        id=2,
        item_id=2,
        shop_id=1,
        title="Camiseta P2",
        url="",
        first_seen_at=now - timedelta(days=20),
        last_seen_at=now,
    )
    c2 = PriceSnapshot(product_id=2, captured_at=now, price_cents=100, sold_count=40, run_id="curr")
    pr2 = PriceSnapshot(
        product_id=2,
        captured_at=now - timedelta(days=5),
        price_cents=100,
        sold_count=50,
        run_id="prev",
    )

    p4 = Product(
        id=4,
        item_id=4,
        shop_id=1,
        title="Camiseta P4",
        url="",
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now,
    )
    c4 = PriceSnapshot(product_id=4, captured_at=now, price_cents=100, sold_count=60, run_id="curr")

    p5 = Product(
        id=5,
        item_id=5,
        shop_id=1,
        title="Camiseta P5",
        url="",
        first_seen_at=now - timedelta(days=1),
        last_seen_at=now,
    )
    c5 = PriceSnapshot(
        product_id=5, captured_at=now, price_cents=100, sold_count=100, run_id="curr"
    )
    pr5 = PriceSnapshot(
        product_id=5,
        captured_at=now - timedelta(days=2),
        price_cents=100,
        sold_count=0,
        run_id="prev",
    )

    session.add_all([p1, p2, p4, p5])
    session.commit()
    session.add_all([c1, pr1, c2, pr2, c4, c5, pr5])
    session.commit()

    products = [
        ScrapedProduct(
            item_id=1,
            shop_id=1,
            title="Camiseta P1",
            url="",
            price_cents=100,
            sold_count=100,
            rating=5.0,
        ),
        ScrapedProduct(
            item_id=2,
            shop_id=1,
            title="Camiseta P2",
            url="",
            price_cents=100,
            sold_count=40,
            rating=5.0,
        ),
        ScrapedProduct(
            item_id=4,
            shop_id=1,
            title="Camiseta P4",
            url="",
            price_cents=100,
            sold_count=60,
            rating=5.0,
        ),
        ScrapedProduct(
            item_id=5,
            shop_id=1,
            title="Camiseta P5",
            url="",
            price_cents=100,
            sold_count=100,
            rating=5.0,
        ),
    ]

    report = analyze_trends(
        products, session=session, run_id="curr", client=FakeLLM([json.dumps({"clusters": []})])
    )

    vels = {ap.product.item_id: ap.velocity_metrics for ap in report.products}

    assert vels[1].delta_sold == 50
    assert vels[1].days_elapsed == 10.0
    assert vels[1].velocity_per_day == 5.0
    assert not vels[1].is_new

    assert vels[2].delta_sold == 0
    assert vels[2].velocity_per_day == 0.0

    assert vels[4].delta_sold == 60
    assert vels[4].days_elapsed == 2.0
    assert vels[4].velocity_per_day == 30.0
    assert vels[4].is_new
    assert vels[4].is_breakout

    assert vels[5].velocity_per_day == 50.0
    assert vels[5].is_breakout
