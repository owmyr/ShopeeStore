import base64
import json
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from core.config import get_settings

logger = logging.getLogger(__name__)


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
        product["base64_image"] = _image_to_base64(img_path)
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
