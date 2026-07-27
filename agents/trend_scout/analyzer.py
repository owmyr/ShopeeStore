"""Trend analysis: dedupe, ranking, price bands, LLM theme clustering.

Pure module - no DB access (persistence lives in agent.py).
LLM access goes through core.llm with max 25 titles per call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from agents.trend_scout.prompts import (
    CLUSTER_SYSTEM,
    NORMALIZE_SYSTEM,
    cluster_user_prompt,
    normalize_user_prompt,
)
from agents.trend_scout.scraper import ScrapedProduct
from core import llm

log = logging.getLogger(__name__)

BATCH_SIZE = 25  # hard rule: max titles per LLM call


@dataclass
class AnalyzedProduct:
    product: ScrapedProduct
    theme: str | None = None


@dataclass
class TrendReport:
    products: list[AnalyzedProduct] = field(default_factory=list)
    price_p25_cents: int = 0
    price_p50_cents: int = 0
    price_p75_cents: int = 0
    theme_counts: list[tuple[str, int]] = field(default_factory=list)  # sorted desc


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
            raw = llm.chat_json(CLUSTER_SYSTEM, cluster_user_prompt(batch), client=client)
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
        raw = llm.chat_json(NORMALIZE_SYSTEM, normalize_user_prompt(unique), client=client)
        parsed = _NormalizeOut.model_validate(raw)
    except (llm.LLMOutputError, ValidationError) as exc:
        log.warning("theme normalization failed, keeping originals: %s", exc)
        return {t: t for t in unique}
    mapping = {t: t for t in unique}
    for entry in parsed.mapping:
        if entry.original in mapping and entry.canonical:
            mapping[entry.original] = entry.canonical
    return mapping


def analyze(products: list[ScrapedProduct], *, client: Any | None = None) -> TrendReport:
    """Full pipeline: dedupe -> rank by sold_count -> price bands -> themes."""
    unique = dedupe(products)
    ranked = sorted(unique, key=lambda p: p.sold_count, reverse=True)

    prices = sorted(p.price_cents for p in ranked)
    report = TrendReport(
        price_p25_cents=percentile(prices, 0.25),
        price_p50_cents=percentile(prices, 0.50),
        price_p75_cents=percentile(prices, 0.75),
    )

    titles = [p.title for p in ranked]
    themes = cluster_titles(titles, client=client) if titles else {}
    canonical = normalize_themes(list(themes.values()), client=client) if themes else {}

    counts: dict[str, int] = {}
    analyzed: list[AnalyzedProduct] = []
    for idx, product in enumerate(ranked):
        theme = themes.get(idx)
        if theme:
            theme = canonical.get(theme, theme)
        analyzed.append(AnalyzedProduct(product=product, theme=theme))
        if theme:
            counts[theme] = counts.get(theme, 0) + 1

    report.products = analyzed
    report.theme_counts = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return report
