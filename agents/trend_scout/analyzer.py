"""Trend analysis: dedupe, ranking, price bands, LLM theme clustering.

Pure module - no DB access (persistence lives in agent.py).
LLM access goes through core.llm with max 25 titles per call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from agents.trend_scout.filter import is_plain
from agents.trend_scout.prompts import (
    CLUSTER_SYSTEM,
    NAO_ESTAMPADA,
    NORMALIZE_SYSTEM,
    cluster_user_prompt,
    normalize_user_prompt,
)
from agents.trend_scout.scraper import ScrapedProduct
from core import llm
from core.config import get_settings

log = logging.getLogger(__name__)

class VelocityMetrics(BaseModel):
    delta_sold: int = 0
    days_elapsed: float = 0.0
    velocity_per_day: float = 0.0
    is_breakout: bool = False
    is_new: bool = False


BATCH_SIZE = (
    75 if get_settings().llm_provider == "gemini" else 25
)  # hard rule: max titles per LLM call


@dataclass
class AnalyzedProduct:
    product: ScrapedProduct
    theme: str | None = None
    velocity_metrics: VelocityMetrics = field(default_factory=VelocityMetrics)


@dataclass
class TrendReport:
    products: list[AnalyzedProduct] = field(default_factory=list)  # printed only
    price_p25_cents: int = 0
    price_p50_cents: int = 0
    price_p75_cents: int = 0
    theme_counts: list[tuple[str, int]] = field(default_factory=list)  # sorted desc
    theme_velocities: list[tuple[str, float]] = field(default_factory=list)
    breakout_products: list[dict[str, Any]] = field(default_factory=list)
    printed_count: int = 0
    excluded_plain_count: int = 0


class _ClusterOut(BaseModel):
    theme: str
    indices: list[int]
    why: str = ""


class _BatchOut(BaseModel):
    clusters: list[_ClusterOut]


class _MapEntry(BaseModel):
    original: str
    canonical: str


class _NormalizeOut(BaseModel):
    mapping: list[_MapEntry]


def percentile(sorted_vals: list[int], p: float) -> int:
    """Linear-interpolation percentile. Expects pre-sorted input."""
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo))


def dedupe(products: list[ScrapedProduct]) -> list[ScrapedProduct]:
    """One entry per item_id (first occurrence wins)."""
    seen: dict[int, ScrapedProduct] = {}
    for p in products:
        seen.setdefault(p.item_id, p)
    return list(seen.values())


def cluster_titles(titles: list[str], *, client: Any | None = None) -> dict[int, str]:
    """Map title index -> theme. Batches of BATCH_SIZE; failed batches are
    logged and left unclustered (never crash the run on LLM output)."""
    mapping: dict[int, str] = {}
    for start in range(0, len(titles), BATCH_SIZE):
        batch = titles[start : start + BATCH_SIZE]
        try:
            raw = llm.chat_json(
                CLUSTER_SYSTEM, cluster_user_prompt(batch), client=client, response_model=_BatchOut
            )
            parsed = _BatchOut.model_validate(raw)
        except (llm.LLMOutputError, ValidationError) as exc:
            log.warning("clustering batch %d-%d failed: %s", start, start + len(batch), exc)
            continue
        for cluster in parsed.clusters:
            for local_idx in cluster.indices:
                global_idx = start + local_idx - 1  # prompt indices are 1-based
                if 0 <= global_idx < len(titles):
                    mapping[global_idx] = cluster.theme
    return mapping


def normalize_themes(themes: list[str], *, client: Any | None = None) -> dict[str, str]:
    """Map each theme to a canonical label (one LLM call). Batches invent
    their own labels for the same concept; this merges synonyms. Falls back
    to identity mapping on any LLM failure."""
    unique = sorted(set(themes))
    if len(unique) <= 3:
        return {t: t for t in unique}
    try:
        raw = llm.chat_json(
            NORMALIZE_SYSTEM,
            normalize_user_prompt(unique),
            client=client,
            response_model=_NormalizeOut,
        )
        parsed = _NormalizeOut.model_validate(raw)
    except (llm.LLMOutputError, ValidationError) as exc:
        log.warning("theme normalization failed, keeping originals: %s", exc)
        return {t: t for t in unique}
    mapping = {t: t for t in unique}
    for entry in parsed.mapping:
        if entry.original in mapping and entry.canonical:
            mapping[entry.original] = entry.canonical
    return mapping


def analyze_trends(
    products: list[ScrapedProduct],
    session: Any | None = None,
    *,
    run_id: str | None = None,
    client: Any | None = None,
) -> TrendReport:
    """Full pipeline with deep velocity integration."""
    velocity_map: dict[int, VelocityMetrics] = {}

    if session and run_id:
        from sqlmodel import select

        from core.models import PriceSnapshot, Product

        now = datetime.now(UTC).replace(tzinfo=None)
        item_ids = [p.item_id for p in products]

        if item_ids:
            db_products = session.exec(select(Product).where(Product.item_id.in_(item_ids))).all()
            product_ids = [p.id for p in db_products if p.id is not None]

            current_snapshots = session.exec(
                select(PriceSnapshot).where(
                    PriceSnapshot.product_id.in_(product_ids), PriceSnapshot.run_id == run_id
                )
            ).all()
            snapshots_map = {
                snap.product_id: snap for snap in current_snapshots if snap.product_id is not None
            }

            prior_snapshots: dict[int, PriceSnapshot] = {}
            if product_ids:
                stmt = (
                    select(PriceSnapshot)
                    .where(
                        PriceSnapshot.product_id.in_(product_ids),
                        PriceSnapshot.run_id != run_id,
                    )
                    .order_by(PriceSnapshot.captured_at.desc())
                )
                results = session.exec(stmt).all()
                for snapshot in results:
                    if snapshot.product_id not in prior_snapshots:
                        prior_snapshots[snapshot.product_id] = snapshot

            velocities_by_db_id = {}
            for product in db_products:
                if product.id is None:
                    continue

                current_snapshot = snapshots_map.get(product.id)
                if not current_snapshot:
                    continue

                prior_snapshot = prior_snapshots.get(product.id)

                if prior_snapshot:
                    delta_sold = max(0, current_snapshot.sold_count - prior_snapshot.sold_count)
                    days_elapsed = max(
                        (now - prior_snapshot.captured_at).total_seconds() / 86400.0,
                        1.0 / 24.0,
                    )
                    velocity_per_day = round(delta_sold / days_elapsed, 1)
                    is_new = False
                else:
                    days_since_first_seen = max(
                        (now - product.first_seen_at).total_seconds() / 86400.0, 1.0
                    )
                    velocity_per_day = round(current_snapshot.sold_count / days_since_first_seen, 1)
                    delta_sold = current_snapshot.sold_count
                    days_elapsed = round(days_since_first_seen, 1)
                    is_new = True

                velocities_by_db_id[product.id] = {
                    "delta_sold": delta_sold,
                    "days_elapsed": days_elapsed,
                    "velocity_per_day": velocity_per_day,
                    "is_new": is_new,
                    "is_breakout": False,
                }

            valid_velocities = [
                v["velocity_per_day"]
                for v in velocities_by_db_id.values()
                if v["velocity_per_day"] > 0
            ]

            threshold = 20.0
            if valid_velocities:
                valid_velocities.sort()
                idx = int(len(valid_velocities) * 0.9)
                top_10_threshold = valid_velocities[idx]
                threshold = min(threshold, top_10_threshold)

            for v in velocities_by_db_id.values():
                if v["velocity_per_day"] > 0 and v["velocity_per_day"] >= threshold:
                    v["is_breakout"] = True

            for p in db_products:
                if p.id in velocities_by_db_id:
                    v_dict = velocities_by_db_id[p.id]
                    velocity_map[p.item_id] = VelocityMetrics(
                        delta_sold=v_dict["delta_sold"],
                        days_elapsed=v_dict["days_elapsed"],
                        velocity_per_day=v_dict["velocity_per_day"],
                        is_breakout=v_dict["is_breakout"],
                        is_new=v_dict["is_new"],
                    )

    return analyze(products, client=client, velocity_map=velocity_map)


def analyze(
    products: list[ScrapedProduct],
    *,
    client: Any | None = None,
    velocity_map: dict[int, VelocityMetrics] | None = None,
) -> TrendReport:
    """Full pipeline: dedupe -> drop plains -> rank -> price bands -> themes.

    Plain (printless) shirts are excluded from the report entirely - they are
    useless to a print store. The LLM may further tag stragglers as
    "nao-estampada"; those stay in `products` (visible) but never in
    `theme_counts`."""
    unique = dedupe(products)
    printed = [p for p in unique if not is_plain(p.title)]
    ranked = sorted(printed, key=lambda p: p.sold_count, reverse=True)

    prices = sorted(p.price_cents for p in ranked)
    report = TrendReport(
        price_p25_cents=percentile(prices, 0.25),
        price_p50_cents=percentile(prices, 0.50),
        price_p75_cents=percentile(prices, 0.75),
        printed_count=len(printed),
        excluded_plain_count=len(unique) - len(printed),
    )

    titles = [p.title for p in ranked]
    themes = cluster_titles(titles, client=client) if titles else {}
    canonical = normalize_themes(list(themes.values()), client=client) if themes else {}

    counts: dict[str, int] = {}
    theme_vels: dict[str, float] = {}
    analyzed: list[AnalyzedProduct] = []
    for idx, product in enumerate(ranked):
        theme = themes.get(idx)
        if theme:
            theme = canonical.get(theme, theme)
        vel = (
            velocity_map.get(product.item_id, VelocityMetrics())
            if velocity_map
            else VelocityMetrics()
        )
        analyzed.append(AnalyzedProduct(product=product, theme=theme, velocity_metrics=vel))

        velocity_per_day = vel.velocity_per_day

        if theme and theme != NAO_ESTAMPADA:
            counts[theme] = counts.get(theme, 0) + 1
            theme_vels[theme] = theme_vels.get(theme, 0.0) + velocity_per_day

    report.products = analyzed
    report.theme_counts = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    report.theme_velocities = sorted(theme_vels.items(), key=lambda kv: (-kv[1], kv[0]))

    breakouts = []
    for ap in analyzed:
        p = ap.product
        vel = velocity_map.get(p.item_id, VelocityMetrics()) if velocity_map else VelocityMetrics()
        if vel.is_breakout:
            breakouts.append(
                {
                    "item_id": p.item_id,
                    "shop_id": p.shop_id,
                    "title": p.title,
                    "url": p.url,
                    "price_cents": p.price_cents,
                    "sold_count": p.sold_count,
                    "rating": p.rating,
                    "theme": ap.theme,
                    "image_url": p.image_url,
                    "velocity_per_day": vel.velocity_per_day,
                    "delta_sold": vel.delta_sold,
                    "days_elapsed": vel.days_elapsed,
                    "is_breakout": True,
                    "is_new": vel.is_new,
                }
            )

    report.breakout_products = sorted(breakouts, key=lambda x: x["velocity_per_day"], reverse=True)[
        :15
    ]

    return report
