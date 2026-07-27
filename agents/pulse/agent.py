"""Pulse agent: daily quick scrape (top ~20) + spike detection.

Cheap radar between weekly deep runs. No LLM - persistence and diffing only.
Spikes = products never seen before, or sold_count jumps vs the previous
snapshot. Output: data/pulse/<ts>.json + ledger entry.

Usage: python -m agents.pulse.agent [--max N]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import select

from agents.trend_scout import scraper
from agents.trend_scout.agent import _persist
from core import db, ledger
from core.config import get_settings
from core.models import PriceSnapshot, Product

log = logging.getLogger(__name__)

AGENT_NAME = "pulse"
SPIKE_JUMP_ABS = 500  # sold_count jump that flags a spike


def detect_spikes(
    products: list[scraper.ScrapedProduct],
    previous: dict[int, PriceSnapshot],
    *,
    jump_abs: int = SPIKE_JUMP_ABS,
) -> list[dict]:
    """New products or big sold jumps vs previous snapshots."""
    spikes: list[dict] = []
    for p in products:
        prev = previous.get(p.item_id)
        if prev is None:
            spikes.append({"item_id": p.item_id, "title": p.title, "kind": "new",
                           "sold": p.sold_count, "jump": None})
        elif p.sold_count - prev.sold_count >= jump_abs:
            spikes.append({"item_id": p.item_id, "title": p.title, "kind": "jump",
                           "sold": p.sold_count, "jump": p.sold_count - prev.sold_count})
    return spikes


def run_once(max_products: int = 20) -> Path:
    settings = get_settings()
    db.init_db()

    with ledger.run(AGENT_NAME, {"max_products": max_products}) as handle:
        products = scraper.scrape_best_sellers(max_products=max_products)

        with db.session_scope() as s:
            # map item_id -> product row for previous-snapshot lookup
            previous: dict[int, PriceSnapshot] = {}
            for p in products:
                row = s.exec(select(Product).where(Product.item_id == p.item_id)).first()
                if row is not None:
                    snap = s.exec(
                        select(PriceSnapshot)
                        .where(PriceSnapshot.product_id == row.id)
                        .order_by(PriceSnapshot.captured_at.desc())  # type: ignore[attr-defined]
                    ).first()
                    if snap is not None:
                        previous[p.item_id] = snap

        spikes = detect_spikes(products, previous)
        _persist(products, handle.run_id)

        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        out_dir = settings.data_dir / "pulse"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{ts}.json"
        out_file.write_text(
            json.dumps(
                {
                    "generated_at": ts,
                    "product_count": len(products),
                    "spikes": spikes,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        log.info("pulse: %d products, %d spikes -> %s", len(products), len(spikes), out_file)
        handle.set_outputs(str(out_file))
    return out_file


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Pulse agent (daily spike radar)")
    parser.add_argument("--max", type=int, default=20, help="products to scrape")
    args = parser.parse_args()
    out = run_once(max_products=args.max)
    print(f"pulse: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
