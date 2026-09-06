"""Image Harvester orchestration.

Reads the latest Trend Scout report (themes + ranking), pulls image URLs
from the DB, downloads the top-N PRINTED product images into theme-segregated
folders (data/reference/<theme-slug>/<item_id>.jpg), and records them in the
product_image table. Plain shirts and "nao-estampada" items are skipped -
the reference folder feeds the design agent and must contain prints only.

Usage: python -m agents.image_harvester.agent [--max N] [--force]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlmodel import Session, select

from agents.image_harvester import downloader
from agents.image_harvester.downloader import download_image
from agents.trend_scout.filter import is_plain, theme_slug
from agents.trend_scout.prompts import NAO_ESTAMPADA
from core import db, ledger
from core.config import get_settings
from core.models import Product, ProductImage

log = logging.getLogger(__name__)

AGENT_NAME = "image_harvester"
IDEMPOTENCY_HOURS = 24


def _latest_report() -> tuple[Path, dict] | None:
    reports = get_settings().data_dir / "reports"
    if not reports.exists():
        return None
    dirs = sorted(d for d in reports.iterdir() if (d / "report.json").exists())
    if not dirs:
        return None
    latest = dirs[-1]
    return latest, json.loads((latest / "report.json").read_text(encoding="utf-8"))


def _image_url_from_db(s: Session, item_id: int) -> str:
    row = s.exec(select(Product).where(Product.item_id == item_id)).first()
    return row.image_url if row else ""


def _record_image(s: Session, item: dict, dest: Path, run_id: str) -> None:
    product = s.exec(select(Product).where(Product.item_id == item["item_id"])).first()
    if product is None:
        return  # orphan: trend scout didn't persist it; skip
    now = datetime.now(UTC).replace(tzinfo=None)
    row = s.exec(select(ProductImage).where(ProductImage.product_id == product.id)).first()
    if row is None:
        row = ProductImage(product_id=product.id, path=str(dest), downloaded_at=now, run_id=run_id)
    else:
        row.path = str(dest)
        row.downloaded_at = now
        row.run_id = run_id
    row.theme = item.get("theme") or ""
    s.add(row)


def run_once(
    max_images: int = 50,
    *,
    force: bool = False,
) -> Path | None:
    settings = get_settings()
    db.init_db()

    found = _latest_report()
    if found is None:
        raise RuntimeError("no trend scout report found - run trend_scout first")
    report_dir, payload = found

    inputs = {"report": report_dir.name, "max_images": max_images}
    if not force:
        last = ledger.last_successful_run(AGENT_NAME, inputs)
        if (
            last
            and last.started_at
            and (
                datetime.now(UTC).replace(tzinfo=None) - last.started_at
                < timedelta(hours=IDEMPOTENCY_HOURS)
            )
        ):
            log.info("skip: identical harvest succeeded recently")
            return Path(last.outputs_path) if last.outputs_path else None

    with ledger.run(AGENT_NAME, inputs) as handle:
        reference_dir = settings.data_dir / "reference"
        candidates = sorted(
            payload.get("products", []),
            key=lambda p: (p.get("velocity_per_day", 0.0), p.get("sold_count", 0)),
            reverse=True,
        )
        items = [
            it
            for it in candidates
            if not is_plain(it.get("title", "")) and it.get("theme") != NAO_ESTAMPADA
        ][:max_images]

        downloaded = 0
        with db.session_scope() as s:
            with httpx.Client(
                headers=downloader.HEADERS, follow_redirects=True, timeout=30.0
            ) as client:
                for item in items:
                    url = item.get("image_url") or _image_url_from_db(s, item["item_id"])
                    if not url:
                        continue
                    slug = theme_slug(item.get("theme") or "")
                    dest = reference_dir / slug / f"{item['item_id']}.jpg"
                    if download_image(url, dest, client=client):
                        downloaded += 1
                        _record_image(s, item, dest, handle.run_id)
            s.commit()

        log.info("harvested %d/%d images -> %s", downloaded, len(items), reference_dir)
        handle.set_outputs(str(reference_dir))
    return reference_dir


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Image Harvester agent")
    parser.add_argument("--max", type=int, default=50, help="max images (default 50)")
    parser.add_argument("--force", action="store_true", help="ignore idempotency skip")
    args = parser.parse_args()
    out = run_once(max_images=args.max, force=args.force)
    print(f"images: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
