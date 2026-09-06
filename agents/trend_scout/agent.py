"""Trend Scout orchestration: scrape -> persist -> analyze -> report.

Idempotent: an identical successful run within IDEMPOTENCY_HOURS is skipped
(ledger inputs_hash match). Every run is recorded in the agent ledger.

Usage: python -m agents.trend_scout.agent [--dry-run] [--max N]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless PNG rendering
import matplotlib.pyplot as plt
from sqlmodel import select

from agents.trend_scout import analyzer, scraper
from agents.trend_scout.analyzer import TrendReport
from agents.trend_scout.scraper import ScrapedProduct
from core import db, ledger
from core.config import get_settings
from core.models import PriceSnapshot, Product

log = logging.getLogger(__name__)

AGENT_NAME = "trend_scout"
IDEMPOTENCY_HOURS = 24


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _persist(products: list[ScrapedProduct], run_id: str) -> None:
    """Upsert products + append one price snapshot per product."""
    now = _utcnow_naive()
    with db.session_scope() as s:
        for p in products:
            stmt = select(Product).where(Product.item_id == p.item_id, Product.shop_id == p.shop_id)
            row = s.exec(stmt).first()
            if row is None:
                row = Product(
                    item_id=p.item_id,
                    shop_id=p.shop_id,
                    title=p.title,
                    url=p.url,
                    image_url=p.image_url,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                s.add(row)
                s.commit()
                s.refresh(row)
            else:
                row.title = p.title
                row.last_seen_at = now
                if p.image_url:
                    row.image_url = p.image_url
                s.add(row)
                s.commit()
                s.refresh(row)
            s.add(
                PriceSnapshot(
                    product_id=row.id,
                    captured_at=now,
                    price_cents=p.price_cents,
                    sold_count=p.sold_count,
                    rating=p.rating,
                    run_id=run_id,
                )
            )
        s.commit()


def _brl(cents: int) -> str:
    return f"R$ {cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _write_report(report: TrendReport) -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = get_settings().data_dir / "reports" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": ts,
        "product_count": len(report.products),
        "printed_count": report.printed_count,
        "excluded_plain_count": report.excluded_plain_count,
        "price_p25_cents": report.price_p25_cents,
        "price_p50_cents": report.price_p50_cents,
        "price_p75_cents": report.price_p75_cents,
        "theme_counts": report.theme_counts,
        "theme_velocities": report.theme_velocities,
        "breakout_products": report.breakout_products,
        "products": [
            {
                "item_id": ap.product.item_id,
                "shop_id": ap.product.shop_id,
                "title": ap.product.title,
                "url": ap.product.url,
                "price_cents": ap.product.price_cents,
                "sold_count": ap.product.sold_count,
                "rating": ap.product.rating,
                "theme": ap.theme,
                "image_url": ap.product.image_url,
                "velocity_per_day": ap.velocity_metrics.get("velocity_per_day", 0.0),
                "delta_sold": ap.velocity_metrics.get("delta_sold", 0),
                "days_elapsed": ap.velocity_metrics.get("days_elapsed", 0.0),
                "is_breakout": ap.velocity_metrics.get("is_breakout", False),
                "is_new": ap.velocity_metrics.get("is_new", False),
            }
            for ap in report.products
        ],
    }
    (out_dir / "report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        f"# Trend Scout Report - {ts}",
        "",
        f"Printed products analyzed: {report.printed_count} "
        f"(excluded plain: {report.excluded_plain_count})",
        "",
        "## Price bands",
        f"- p25: {_brl(report.price_p25_cents)}",
        f"- p50 (median): {_brl(report.price_p50_cents)}",
        f"- p75: {_brl(report.price_p75_cents)}",
        "",
        "## Themes",
    ]
    lines += [f"- {theme}: {count}" for theme, count in report.theme_counts] or ["- (none)"]
    lines += [
        "",
        "## Top products (by sold)",
        "",
        "| Sold | Price | Theme | Title |",
        "|---|---|---|---|",
    ]
    for ap in report.products[:50]:
        p = ap.product
        lines.append(f"| {p.sold_count} | {_brl(p.price_cents)} | {ap.theme or '-'} | {p.title} |")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    if report.products:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist([ap.product.price_cents / 100 for ap in report.products], bins=30)
        ax.set_xlabel("Price (BRL)")
        ax.set_ylabel("Products")
        ax.set_title("Price distribution")
        fig.tight_layout()
        fig.savefig(out_dir / "prices.png", dpi=100)
        plt.close(fig)

    if report.theme_counts:
        themes, counts = zip(*report.theme_counts[:15], strict=True)
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh(list(reversed(themes)), list(reversed(counts)))
        ax.set_title("Theme frequency")
        fig.tight_layout()
        fig.savefig(out_dir / "themes.png", dpi=100)
        plt.close(fig)

    return out_dir


def run_once(
    max_products: int | None = None,
    *,
    dry_run: bool = False,
    client: Any | None = None,
    force: bool = False,
) -> Path | None:
    """One full Trend Scout cycle. Returns the report directory (or the last
    successful run's directory if skipped as redundant)."""
    settings = get_settings()
    db.init_db()

    inputs = {
        "max_products": max_products or settings.scrape_max_products,
        "dry_run": dry_run,
    }
    if not force:
        last = ledger.last_successful_run(AGENT_NAME, inputs)
        if (
            last
            and last.started_at
            and (_utcnow_naive() - last.started_at < timedelta(hours=IDEMPOTENCY_HOURS))
        ):
            log.info("skip: identical run succeeded %s ago", _utcnow_naive() - last.started_at)
            return Path(last.outputs_path) if last.outputs_path else None

    with ledger.run(AGENT_NAME, inputs) as handle:
        products = scraper.scrape_best_sellers(max_products=max_products, dry_run=dry_run)
        _persist(products, handle.run_id)

        # Velocity logic
        now = _utcnow_naive()
        with db.session_scope() as s:
            # Re-fetch products to get their db IDs
            item_ids = [p.item_id for p in products]
            db_products = s.exec(select(Product).where(Product.item_id.in_(item_ids))).all()

            # Fetch current snapshots
            product_ids = [p.id for p in db_products if p.id is not None]
            current_snapshots = s.exec(
                select(PriceSnapshot).where(
                    PriceSnapshot.product_id.in_(product_ids), PriceSnapshot.run_id == handle.run_id
                )
            ).all()
            snapshots_map = {
                snap.product_id: snap for snap in current_snapshots if snap.product_id is not None
            }

            from agents.trend_scout.velocity import compute_product_velocities, get_prior_snapshots

            prior_snapshots = get_prior_snapshots(s, product_ids, handle.run_id)
            velocities_by_db_id = compute_product_velocities(
                db_products, snapshots_map, prior_snapshots, now
            )

            # map db_id back to item_id for analyzer
            velocity_map = {}
            for p in db_products:
                if p.id in velocities_by_db_id:
                    velocity_map[p.item_id] = velocities_by_db_id[p.id]

        report = analyzer.analyze(products, client=client, velocity_map=velocity_map)
        out_dir = _write_report(report)
        handle.set_outputs(str(out_dir))
    log.info("trend scout run complete -> %s", out_dir)
    return out_dir


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Trend Scout agent")
    parser.add_argument("--dry-run", action="store_true", help="scrape only 5 products")
    parser.add_argument("--max", type=int, default=None, help="max products")
    parser.add_argument("--force", action="store_true", help="ignore idempotency skip")
    args = parser.parse_args()
    out = run_once(max_products=args.max, dry_run=args.dry_run, force=args.force)
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
