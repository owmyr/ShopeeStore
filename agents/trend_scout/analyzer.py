"""Trend analysis: dedupe, ranking, price bands, LLM theme clustering.

Pure module - no DB access (persistence lives in agent.py).
LLM access goes through core.llm with max 25 titles per call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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

BATCH_SIZE = (
    75 if get_settings().llm_provider == "gemini" else 25
)  # hard rule: max titles per LLM call


@dataclass
class AnalyzedProduct:
    product: ScrapedProduct
    theme: str | None = None
    velocity_metrics: dict[str, Any] = field(default_factory=dict)


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


def analyze(
    products: list[ScrapedProduct],
    *,
    client: Any | None = None,
    velocity_map: dict[int, dict[str, Any]] | None = None,
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
        vel = velocity_map.get(product.item_id, {}) if velocity_map else {}
        analyzed.append(AnalyzedProduct(product=product, theme=theme, velocity_metrics=vel))

        velocity_per_day = vel.get("velocity_per_day", 0.0)

        if theme and theme != NAO_ESTAMPADA:
            counts[theme] = counts.get(theme, 0) + 1
            theme_vels[theme] = theme_vels.get(theme, 0.0) + velocity_per_day

    report.products = analyzed
    report.theme_counts = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    report.theme_velocities = sorted(theme_vels.items(), key=lambda kv: (-kv[1], kv[0]))

    breakouts = []
    for ap in analyzed:
        p = ap.product
        vel = velocity_map.get(p.item_id, {}) if velocity_map else {}
        if vel.get("is_breakout", False):
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
                    "velocity_per_day": vel.get("velocity_per_day", 0.0),
                    "delta_sold": vel.get("delta_sold", 0),
                    "days_elapsed": vel.get("days_elapsed", 0.0),
                    "is_breakout": True,
                    "is_new": vel.get("is_new", False),
                }
            )

    report.breakout_products = sorted(breakouts, key=lambda x: x["velocity_per_day"], reverse=True)[
        :15
    ]

    return report
