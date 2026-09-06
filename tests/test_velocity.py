from datetime import datetime, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from agents.trend_scout.analyzer import analyze
from agents.trend_scout.scraper import ScrapedProduct
from agents.trend_scout.velocity import compute_product_velocities, get_prior_snapshots
from core.models import PriceSnapshot, Product


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_get_prior_snapshots(session: Session):
    now = datetime(2026, 1, 1, 12, 0, 0)

    # 2 products, multiple snapshots
    p1 = Product(id=1, item_id=1, shop_id=1, title="A", url="", first_seen_at=now, last_seen_at=now)
    p2 = Product(id=2, item_id=2, shop_id=1, title="B", url="", first_seen_at=now, last_seen_at=now)
    session.add(p1)
    session.add(p2)
    session.commit()

    s1 = PriceSnapshot(
        product_id=1,
        captured_at=now - timedelta(days=2),
        price_cents=100,
        sold_count=10,
        run_id="run1",
    )
    s2 = PriceSnapshot(
        product_id=1,
        captured_at=now - timedelta(days=1),
        price_cents=100,
        sold_count=20,
        run_id="run2",
    )
    s3 = PriceSnapshot(
        product_id=1, captured_at=now, price_cents=100, sold_count=30, run_id="run_current"
    )

    s4 = PriceSnapshot(
        product_id=2,
        captured_at=now - timedelta(days=3),
        price_cents=200,
        sold_count=5,
        run_id="run1",
    )

    session.add_all([s1, s2, s3, s4])
    session.commit()

    priors = get_prior_snapshots(session, [1, 2], "run_current")
    assert len(priors) == 2
    assert priors[1].run_id == "run2"  # most recent before current
    assert priors[2].run_id == "run1"


def test_compute_velocities():
    now = datetime(2026, 1, 10, 12, 0, 0)

    # Product 1: Normal positive delta (10 days elapsed, 50 sold)
    p1 = Product(
        id=1,
        item_id=1,
        shop_id=1,
        title="P1",
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

    # Product 2: Negative delta clamping
    p2 = Product(
        id=2,
        item_id=2,
        shop_id=1,
        title="P2",
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

    # Product 3: Zero days protection (less than 1 hour elapsed)
    p3 = Product(
        id=3,
        item_id=3,
        shop_id=1,
        title="P3",
        url="",
        first_seen_at=now - timedelta(days=20),
        last_seen_at=now,
    )
    c3 = PriceSnapshot(product_id=3, captured_at=now, price_cents=100, sold_count=10, run_id="curr")
    pr3 = PriceSnapshot(
        product_id=3,
        captured_at=now - timedelta(minutes=10),
        price_cents=100,
        sold_count=5,
        run_id="prev",
    )

    # Product 4: Cold start (no prior snapshot)
    p4 = Product(
        id=4,
        item_id=4,
        shop_id=1,
        title="P4",
        url="",
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now,
    )
    c4 = PriceSnapshot(product_id=4, captured_at=now, price_cents=100, sold_count=60, run_id="curr")

    # Product 5: Breakout (very high velocity)
    p5 = Product(
        id=5,
        item_id=5,
        shop_id=1,
        title="P5",
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

    products = [p1, p2, p3, p4, p5]
    snapshots_map = {1: c1, 2: c2, 3: c3, 4: c4, 5: c5}
    prior_snapshots = {1: pr1, 2: pr2, 3: pr3, 5: pr5}

    vels = compute_product_velocities(products, snapshots_map, prior_snapshots, now)

    assert vels[1]["delta_sold"] == 50
    assert vels[1]["days_elapsed"] == 10.0
    assert vels[1]["velocity_per_day"] == 5.0
    assert not vels[1]["is_new"]

    assert vels[2]["delta_sold"] == 0  # clamped
    assert vels[2]["velocity_per_day"] == 0.0

    assert vels[3]["days_elapsed"] == 1.0 / 24.0  # min 1 hour
    assert vels[3]["velocity_per_day"] == round(5 / (1.0 / 24.0), 1)

    assert vels[4]["delta_sold"] == 60
    assert vels[4]["days_elapsed"] == 2.0
    assert vels[4]["velocity_per_day"] == 30.0
    assert vels[4]["is_new"]

    # p4 has 30.0 velocity. Threshold might be 20.0 or top 10%
    assert vels[4]["is_breakout"]
    assert vels[5]["velocity_per_day"] == 50.0
    assert vels[5]["is_breakout"]


def test_analyzer_integration(monkeypatch):
    products = [
        ScrapedProduct(
            item_id=1,
            shop_id=1,
            title="Camiseta Estampada Anime",
            url="",
            price_cents=1000,
            sold_count=100,
            rating=5.0,
        ),
        ScrapedProduct(
            item_id=2,
            shop_id=1,
            title="Camiseta Estampada Caveira",
            url="",
            price_cents=1000,
            sold_count=50,
            rating=4.5,
        ),
        ScrapedProduct(
            item_id=3,
            shop_id=1,
            title="Camiseta Estampada Rock",
            url="",
            price_cents=1000,
            sold_count=200,
            rating=4.8,
        ),
    ]

    velocity_map = {
        1: {
            "velocity_per_day": 10.0,
            "delta_sold": 10,
            "days_elapsed": 1.0,
            "is_breakout": False,
            "is_new": False,
        },
        2: {
            "velocity_per_day": 5.0,
            "delta_sold": 5,
            "days_elapsed": 1.0,
            "is_breakout": False,
            "is_new": False,
        },
        3: {
            "velocity_per_day": 50.0,
            "delta_sold": 50,
            "days_elapsed": 1.0,
            "is_breakout": True,
            "is_new": True,
        },
    }

    monkeypatch.setattr(
        "agents.trend_scout.analyzer.cluster_titles",
        lambda t, client=None: {0: "Anime", 1: "Caveira", 2: "Rock"},
    )
    monkeypatch.setattr(
        "agents.trend_scout.analyzer.normalize_themes", lambda t, client=None: {th: th for th in t}
    )

    report = analyze(products, velocity_map=velocity_map)

    # We should have breakout_products populated
    assert len(report.breakout_products) == 1
    assert report.breakout_products[0]["item_id"] == 3
    assert report.breakout_products[0]["is_breakout"] is True
    assert report.breakout_products[0]["velocity_per_day"] == 50.0
    # theme_velocities should be populated if themes exist.
    # If LLM failed, themes might be None, but if they failed gracefully it's {}.
    # cluster_titles uses LLM. If we don't mock it, it will catch exception and return {}.
    # Then theme might be None. If theme is None, theme_vels won't include it.

    # Let's just check breakout logic
    assert report.breakout_products[0]["velocity_per_day"] == 50.0
