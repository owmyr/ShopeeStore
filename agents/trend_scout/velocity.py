"""Sales velocity calculations for Trend Scout."""

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from core.models import PriceSnapshot, Product


def get_prior_snapshots(
    session: Session, product_ids: list[int], current_run_id: str
) -> dict[int, PriceSnapshot]:
    """Batch query prior PriceSnapshots for products.
    Returns the most recent snapshot per product prior to current_run_id.
    """
    if not product_ids:
        return {}

    stmt = (
        select(PriceSnapshot)
        .where(
            PriceSnapshot.product_id.in_(product_ids),
            PriceSnapshot.run_id != current_run_id,
        )
        .order_by(PriceSnapshot.captured_at.desc())
    )
    results = session.exec(stmt).all()

    prior_snapshots: dict[int, PriceSnapshot] = {}
    for snapshot in results:
        if snapshot.product_id not in prior_snapshots:
            prior_snapshots[snapshot.product_id] = snapshot

    return prior_snapshots


def compute_product_velocities(
    products: list[Product],
    snapshots_map: dict[int, PriceSnapshot],
    prior_snapshots: dict[int, PriceSnapshot],
    current_time: datetime,
) -> dict[int, dict[str, Any]]:
    """Compute daily sales velocity for products."""
    velocities: dict[int, dict[str, Any]] = {}

    for product in products:
        if product.id is None:
            continue

        current_snapshot = snapshots_map.get(product.id)
        if not current_snapshot:
            continue

        prior_snapshot = prior_snapshots.get(product.id)

        if prior_snapshot:
            delta_sold = max(0, current_snapshot.sold_count - prior_snapshot.sold_count)
            days_elapsed = max(
                (current_time - prior_snapshot.captured_at).total_seconds() / 86400.0,
                1.0 / 24.0,
            )
            velocity_per_day = round(delta_sold / days_elapsed, 1)
            is_new = False
        else:
            days_since_first_seen = max(
                (current_time - product.first_seen_at).total_seconds() / 86400.0, 1.0
            )
            velocity_per_day = round(current_snapshot.sold_count / days_since_first_seen, 1)
            delta_sold = current_snapshot.sold_count
            days_elapsed = round(days_since_first_seen, 1)
            is_new = True

        velocities[product.id] = {
            "delta_sold": delta_sold,
            "days_elapsed": days_elapsed,
            "velocity_per_day": velocity_per_day,
            "is_new": is_new,
            "is_breakout": False,
        }

    # Detect breakouts
    valid_velocities = [
        v["velocity_per_day"] for v in velocities.values() if v["velocity_per_day"] > 0
    ]

    threshold = 20.0
    if valid_velocities:
        valid_velocities.sort()
        # Top 10% means index = floor(len * 0.9)
        idx = int(len(valid_velocities) * 0.9)
        top_10_threshold = valid_velocities[idx]
        threshold = min(threshold, top_10_threshold)

    for v in velocities.values():
        if v["velocity_per_day"] > 0 and v["velocity_per_day"] >= threshold:
            v["is_breakout"] = True

    return velocities
