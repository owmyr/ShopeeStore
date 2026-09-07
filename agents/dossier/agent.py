import base64
import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from agents.trend_scout.filter import theme_slug as normalize_theme_slug
from core.config import get_settings

logger = logging.getLogger(__name__)

_CDN_HEADERS = {
    "Referer": "https://shopee.com.br/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
}


def _fetch_cdn_image(url: str) -> str | None:
    """Download a Shopee CDN image and return it as a base64 data URI.

    Uses Referer spoofing — Shopee CDN requires a valid shopee.com.br Referer
    header or it returns a 403. Returns None on any network/HTTP error so the
    caller can fall back gracefully.
    """
    try:
        resp = httpx.get(url, headers=_CDN_HEADERS, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(resp.content).decode("utf-8")
        return f"data:{ct};base64,{b64}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("CDN fetch failed for %s: %s", url, exc)
        return None


def _image_to_base64(img_path: Path) -> str:
    """Read an image and convert it to a base64 data URI.

    If the file doesn't exist, returns a placeholder SVG base64.
    """
    if img_path.exists():
        mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime};base64,{b64}"

    svg = (
        '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
        '<rect width="200" height="200" fill="#f8fafc"/>'
        '<circle cx="100" cy="90" r="30" fill="#e2e8f0"/>'
        '<path d="M85 85 L115 100 L85 115 Z" fill="#94a3b8" />'
        '<text x="50%" y="140" font-family="Plus Jakarta Sans, sans-serif" font-weight="600" '
        'font-size="12" fill="#64748b" text-anchor="middle" '
        'letter-spacing="1">MOCKUP PENDENTE</text>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


def get_latest_report_dir() -> Path | None:
    reports = get_settings().data_dir / "reports"
    if not reports.exists():
        return None
    dirs = sorted((d for d in reports.iterdir() if (d / "report.json").exists()))
    return dirs[-1] if dirs else None


def generate_dossier(
    report_dir: Path | None = None, theme_slug: str | None = None, output_pdf: bool = True
) -> Path:
    """Generate an executive dossier in HTML and optionally PDF format.

    Args:
        report_dir: Directory containing the report.json. If None, uses the latest.
        theme_slug: Optional theme to filter the dossier content.
        output_pdf: Whether to generate a PDF using Playwright.

    Returns:
        Path to the generated file (PDF if generated, else HTML).
    """
    if report_dir is None:
        report_dir = get_latest_report_dir()
        if report_dir is None:
            raise FileNotFoundError("No report directories found.")

    report_json_path = report_dir / "report.json"
    if not report_json_path.exists():
        raise FileNotFoundError(f"report.json not found in {report_dir}")

    with open(report_json_path, "r", encoding="utf-8") as f:
        payload = json.loads(f.read())

    products = payload.get("products", [])
    if theme_slug:
        products = [p for p in products if p.get("theme") == theme_slug]

    # Sort products by sold count (descending) and take top 10 for Breakout Graphics
    breakout_products = sorted(products, key=lambda x: x.get("sold_count", 0), reverse=True)[:10]

    reference_dir = get_settings().data_dir / "reference"
    for product in breakout_products:
        item_id = product.get("item_id")
        p_theme = product.get("theme") or "unknown"
        img_path = reference_dir / p_theme / f"{item_id}.jpg"

        if img_path.exists():
            # Happy path: harvester already downloaded this image.
            product["base64_image"] = _image_to_base64(img_path)
        else:
            # Fallback: fetch directly from Shopee's CDN using the scraped URL.
            # This covers breakout products whose theme slug didn't match the
            # harvested folder name, or that were scraped after the last harvest.
            cdn_url = product.get("image_url", "")
            cdn_data = _fetch_cdn_image(cdn_url) if cdn_url else None
            product["base64_image"] = cdn_data or _image_to_base64(img_path)  # SVG if all fails
        product["price_brl"] = product.get("price_cents", 0) / 100
        product["velocity"] = f"+{product.get('sold_count', 0)} peças/dia"  # Mocked velocity

    theme_counts = payload.get("theme_counts", [])
    if theme_slug:
        theme_counts = [t for t in theme_counts if t[0] == theme_slug]

    # Get top 3 themes
    top_themes = theme_counts[:3]
    themes_data = []

    total_printed = payload.get("printed_count", 1)

    for theme_name, count in top_themes:
        # Calculate price percentiles for the theme
        theme_prods = [p for p in payload.get("products", []) if p.get("theme") == theme_name]
        prices = sorted([p.get("price_cents", 0) / 100 for p in theme_prods])

        if prices:
            p25 = prices[len(prices) // 4]
            p50 = prices[len(prices) // 2]
            p75 = prices[(len(prices) * 3) // 4]
        else:
            p25 = p50 = p75 = 0

        themes_data.append(
            {
                "name": theme_name,
                "velocity": f"+{count * 5} peças/dia",  # Mocked velocity
                "volume_share": f"{(count / total_printed) * 100:.1f}%",
                "p25": p25,
                "p50": p50,
                "p75": p75,
            }
        )

    # Prepare template data
    template_data = {
        "date": datetime.strptime(payload.get("generated_at", ""), "%Y%m%dT%H%M%SZ").strftime(
            "%d/%m/%Y"
        )
        if payload.get("generated_at")
        else datetime.now().strftime("%d/%m/%Y"),
        "market_volume": payload.get("product_count", 0),
        "median_price": payload.get("price_p50_cents", 0) / 100,
        "themes": themes_data,
        "breakout_products": breakout_products,
        "theme_filtered": theme_slug,
    }

    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
    template = env.get_template("dossier.html")
    html_content = template.render(**template_data)

    html_path = report_dir / "dossier.html"
    if theme_slug:
        html_path = report_dir / f"dossier_{theme_slug}.html"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if not output_pdf:
        return html_path

    pdf_path = html_path.with_suffix(".pdf")
    png_path = html_path.with_suffix(".png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1200, "height": 1600},
                device_scale_factor=2,
            )
            page.goto(f"file://{html_path.resolve()}")
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
            page.screenshot(path=str(png_path), full_page=True)
            browser.close()
        return pdf_path
    except Exception as e:
        logger.warning("Failed to generate PDF/PNG (Playwright/Chromium issue): %s", e)
        return html_path


def generate_theme_card(theme_slug: str, report_dir: Path | None = None) -> Path:
    """Generate a high-contrast 800x800 square image card for B2B merchant outreach.

    Creates visual proof of niche momentum to spark commercial conversations
    with apparel store owners across WhatsApp and social channels. Showcases
    top breakout designs, niche sales pace, and direct call-to-action.

    Args:
        theme_slug: Category/theme identifier (slug or display name).
        report_dir: Optional custom path to a report folder containing report.json.

    Returns:
        Path to the rendered PNG screenshot card.
    """
    if report_dir is None:
        report_dir = get_latest_report_dir()
        if report_dir is None:
            raise FileNotFoundError("No report directories found.")

    report_json_path = report_dir / "report.json"
    if not report_json_path.exists():
        raise FileNotFoundError(f"report.json not found in {report_dir}")

    with open(report_json_path, "r", encoding="utf-8") as f:
        payload = json.loads(f.read())

    target_slug = normalize_theme_slug(theme_slug)
    all_products = payload.get("products", [])

    def _matches_theme(p: dict) -> bool:
        p_theme = p.get("theme")
        if not p_theme:
            return False
        return (
            p_theme.lower() == theme_slug.lower()
            or normalize_theme_slug(p_theme) == target_slug
        )

    matching_products = [p for p in all_products if _matches_theme(p)]

    def _product_velocity_or_sold(p: dict) -> tuple[float, float]:
        vel = p.get("velocity_per_day")
        sold = p.get("sold_count") or 0
        return (float(vel) if vel is not None else 0.0, float(sold))

    # Sort matching products by velocity_per_day, fallback to sold_count
    sorted_theme_products = sorted(
        matching_products, key=_product_velocity_or_sold, reverse=True
    )

    selected_products = list(sorted_theme_products[:3])

    # If not enough products for the theme, fall back to top breakout products across report
    if len(selected_products) < 3:
        used_ids = {p.get("item_id") for p in selected_products if p.get("item_id") is not None}
        breakouts = payload.get("breakout_products", [])
        candidate_fallbacks = [
            p for p in breakouts if p.get("item_id") not in used_ids
        ]
        sorted_all = sorted(
            all_products, key=_product_velocity_or_sold, reverse=True
        )
        for p in sorted_all:
            if p.get("item_id") not in used_ids and p not in candidate_fallbacks:
                candidate_fallbacks.append(p)

        for p in candidate_fallbacks:
            if len(selected_products) >= 3:
                break
            selected_products.append(p)
            if p.get("item_id") is not None:
                used_ids.add(p.get("item_id"))

    # Resolve image base64, price, and velocity for each selected product
    reference_dir = get_settings().data_dir / "reference"
    formatted_products = []
    for prod in selected_products:
        item_id = prod.get("item_id")
        p_theme = prod.get("theme") or theme_slug
        p_slug = normalize_theme_slug(p_theme)

        img_path = reference_dir / p_slug / f"{item_id}.jpg"
        if not img_path.exists():
            img_path = reference_dir / p_theme / f"{item_id}.jpg"

        if img_path.exists():
            b64_img = _image_to_base64(img_path)
        else:
            cdn_url = prod.get("image_url", "")
            b64_img = _fetch_cdn_image(cdn_url) if cdn_url else None
            if not b64_img:
                b64_img = _image_to_base64(img_path)

        price_cents = prod.get("price_cents", 0)
        price_brl = f"{price_cents / 100:.2f}".replace(".", ",")

        vel = prod.get("velocity_per_day")
        if vel is None:
            vel_val = prod.get("sold_count", 0)
        elif isinstance(vel, (int, float)):
            vel_val = int(vel) if vel == int(vel) else round(vel, 1)
        else:
            vel_val = vel

        formatted_products.append(
            {
                "item_id": item_id,
                "title": prod.get("title", ""),
                "base64_image": b64_img,
                "price_brl": price_brl,
                "velocity_per_day": vel_val,
            }
        )

    # Resolve theme display name, listings count, total velocity, and opportunity badge
    theme_display = theme_slug.replace("-", " ").title()
    listings_count = len(matching_products)
    total_velocity = 0

    for t, cnt in payload.get("theme_counts", []):
        if normalize_theme_slug(t) == target_slug or t.lower() == theme_slug.lower():
            theme_display = t.title()
            listings_count = cnt
            break

    for t, vel in payload.get("theme_velocities", []):
        if normalize_theme_slug(t) == target_slug or t.lower() == theme_slug.lower():
            if isinstance(vel, (int, float)):
                total_velocity = int(vel) if vel == int(vel) else round(vel, 1)
            else:
                total_velocity = vel
            break

    if not total_velocity:
        sum_vel = sum(
            (p.get("velocity_per_day") or p.get("sold_count") or 0) for p in matching_products
        )
        total_velocity = int(round(sum_vel)) if sum_vel else (listings_count * 10)

    # Opportunity metadata
    opp_meta = payload.get("theme_opportunities", {})
    theme_opp = None
    if isinstance(opp_meta, dict):
        theme_opp = opp_meta.get(theme_slug) or opp_meta.get(target_slug)
    elif isinstance(opp_meta, list):
        for item in opp_meta:
            if isinstance(item, dict) and (
                item.get("theme") == theme_slug
                or normalize_theme_slug(item.get("theme", "")) == target_slug
            ):
                theme_opp = item
                break

    opportunity_label = "Alta Procura • Pouca Concorrência"
    badge_color = "emerald"
    if theme_opp and isinstance(theme_opp, dict):
        opportunity_label = theme_opp.get("label", opportunity_label)
        badge_color = theme_opp.get("badge_color", badge_color)

    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
    template = env.get_template("card.html")
    html_content = template.render(
        theme_display=theme_display,
        badge_color=badge_color,
        opportunity_label=opportunity_label,
        total_velocity=total_velocity,
        listings_count=listings_count,
        products=formatted_products,
    )

    output_dir = report_dir / "cards"
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{theme_slug}.html"
    html_path.write_text(html_content, encoding="utf-8")
    png_path = output_dir / f"{theme_slug}.png"

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, channel="chrome")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falling back to default chromium launcher: %s", exc)
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 800})
        page.goto(f"file://{html_path.resolve()}")
        page.screenshot(path=str(png_path), type="png")
        browser.close()

    return png_path

