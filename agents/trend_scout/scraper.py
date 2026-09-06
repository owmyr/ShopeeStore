"""Playwright scraper for Shopee BR best-sellers (camisetas).

Patterns documented in .opencode/skills/shopee-br-scraping/SKILL.md:
- Anchor hrefs `/{name}-i.{shopid}.{itemid}` are the stable extraction key.
- pt-BR prices ("R$ 1.234,56") parsed to integer cents.
- Infinite scroll pagination with polite jittered delays.
- Screenshot to data/ before raising on any error.
- `--dry-run` caps at 5 products for development.

Dev usage: python -m agents.trend_scout.scraper --dry-run

Search keyword comes from config (SCRAPE_KEYWORD, default "camiseta estampada")
so results are biased toward printed shirts at the source.
"""

from __future__ import annotations

import argparse
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import Browser, BrowserContext, Page, Response, sync_playwright

from core.config import get_settings

log = logging.getLogger(__name__)

ITEM_HREF_RE = re.compile(r"-i\.(\d+)\.(\d+)")


def search_url(keyword: str) -> str:
    """Shopee BR search URL sorted by sales for a keyword."""
    return f"https://shopee.com.br/search?keyword={quote(keyword)}&sortBy=sales"


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)

_ANCHOR_DUMP_JS = """() => {
  const out = [];
  document.querySelectorAll('a[href*="-i."]').forEach((a) => {
    const img = a.querySelector("img");
    out.push({ href: a.href, text: a.innerText || "", img: img ? img.src : "" });
  });
  return out;
}"""


class ShopeeAuthError(RuntimeError):
    """Auth state missing or expired - run `python -m agents.trend_scout.scraper --login`."""


@dataclass
class ScrapedProduct:
    item_id: int
    shop_id: int
    title: str
    url: str
    price_cents: int
    sold_count: int
    rating: float | None
    image_url: str = ""


# ---------------------------------------------------------------------------
# Pure parsing helpers (unit-tested without a browser)
# ---------------------------------------------------------------------------

_PRICE_RE = re.compile(r"R\$\s*(\d[\d.]*,\d{2})")
_BARE_PRICE_RE = re.compile(r"(\d[\d.]*,\d{2})")
_DISCOUNT_RE = re.compile(r"^-?\s*\d+\s*%(\s*OFF)?$", re.IGNORECASE)


def parse_price_cents(text: str) -> int | None:
    r"""'R$ 1.234,56' -> 123456. pt-BR: dot=thousands, comma=decimal.

    Handles Shopee's split layout where 'R$' and the number are on
    separate lines (\s matches the newline)."""
    m = _PRICE_RE.search(text) or _BARE_PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return round(float(raw) * 100)
    except ValueError:
        return None


def parse_sold_count(text: str) -> int | None:
    """'1,2 mil vendidos' -> 1200; '10 mil+ vendidos' -> 10000; '50 vendidos' -> 50."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mil)?\s*\+?\s*vendido", text.lower())
    if not m:
        return None
    num = float(m.group(1).replace(",", "."))
    if m.group(2):
        num *= 1000
    return int(num)


def parse_rating(text: str) -> float | None:
    """'4,8' -> 4.8. Strict one-digit-decimal rating in [0, 5]."""
    m = re.fullmatch(r"([0-5])[.,](\d)", text.strip())
    if not m:
        return None
    return float(f"{m.group(1)}.{m.group(2)}")


def parse_item_href(href: str) -> tuple[int, int] | None:
    """'...-i.{shop_id}.{item_id}?...' -> (shop_id, item_id)."""
    m = ITEM_HREF_RE.search(href)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _is_title_line(line: str) -> bool:
    if "R$" in line or _DISCOUNT_RE.match(line):
        return False
    if _BARE_PRICE_RE.fullmatch(line):
        return False
    if parse_sold_count(line) is not None:
        return False
    return parse_rating(line) is None


def parse_card_text(text: str) -> tuple[str, int | None, int | None, float | None]:
    """Split an anchor's innerText block into (title, price_cents, sold, rating).

    Real Shopee card layout (verified 2026-07): discount badge, title,
    'R$' alone on a line, price on the next line, then 'NNN vendidos'."""
    price_cents = parse_price_cents(text)
    sold = parse_sold_count(text)
    title = ""
    rating: float | None = None
    for line in (ln.strip() for ln in text.splitlines() if ln.strip()):
        if rating is None:
            candidate = parse_rating(line)
            if candidate is not None:
                rating = candidate
                continue
        if not title and _is_title_line(line):
            title = line
    return title, price_cents, sold, rating


# ---------------------------------------------------------------------------
# Auth (one-time manual login, persisted session)
# ---------------------------------------------------------------------------


def _new_context(
    pw, *, headless: bool, with_auth: bool, real_chrome: bool = False
) -> tuple[Browser, BrowserContext]:
    """Launch a browser + context with our standard anti-bot fingerprint.

    Always uses the installed Google Chrome binary (channel='chrome') to match
    the exact browser fingerprint Shopee saw during the manual login session.
    Bundled Playwright Chromium gets flagged by /verify/traffic even with a
    valid session because the UA version and capability bits differ.
    """
    settings = get_settings()
    launch_kwargs: dict = {
        "headless": headless,
        # Always use real Chrome — same fingerprint as the login session.
        "channel": "chrome",
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    browser = pw.chromium.launch(**launch_kwargs)
    kwargs: dict = {
        "viewport": {"width": 1366, "height": 768},
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
        "user_agent": USER_AGENT,
    }
    if with_auth:
        kwargs["storage_state"] = str(settings.shopee_auth_path)
    return browser, browser.new_context(**kwargs)


def _is_auth_wall(url: str) -> bool:
    return "/verify/traffic" in url or "/buyer/login" in url


def _is_captcha_wall(url: str) -> bool:
    """Anti-bot slider challenge ("Arraste para completar o quebra-cabeca").

    Distinct from the login wall: the session is valid but flagged (usually
    after heavy scraping). Remedy is the same: re-run --login and solve the
    puzzle in the headed browser."""
    return "/verify/captcha" in url


def _is_login_flow_url(url: str) -> bool:
    """URLs seen while auth is still in progress (not yet logged in)."""
    return _is_auth_wall(url) or "/buyer/signup" in url or "/verify/" in url


def _dismiss_overlays(page: Page) -> None:
    """Best-effort dismissal of blocking overlays (cookie banner, language
    modal). Never fails - overlays may not exist."""
    for text in ("Português (BR)", "Aceitar todos os cookies"):
        try:
            page.get_by_text(text, exact=False).first.click(timeout=1500)
            page.wait_for_timeout(400)
        except Exception:  # noqa: BLE001 - overlay may not exist
            pass


def login(timeout_sec: int = 600) -> Path:
    """One-time manual login. Opens a headed browser; the user logs in
    (captcha/OTP included); session cookies are persisted to SHOPEE_AUTH_PATH."""
    settings = get_settings()
    settings.shopee_auth_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser, context = _new_context(pw, headless=False, with_auth=False, real_chrome=True)
        try:
            page = context.new_page()
            page.goto("https://shopee.com.br/", wait_until="domcontentloaded", timeout=60000)
            _dismiss_overlays(page)
            page.goto(
                "https://shopee.com.br/buyer/login",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(1500)
            _dismiss_overlays(page)  # language modal can appear on login page too
            print(">>> Faca login na janela do navegador. <<<", flush=True)
            print(
                ">>> Se concluir o login e nao detectar, navegue para "
                "https://shopee.com.br em uma aba dessa janela. <<<",
                flush=True,
            )
            deadline = time.monotonic() + timeout_sec
            detected: Page | None = None
            last_report = 0.0
            while time.monotonic() < deadline:
                for p in context.pages:
                    try:
                        url = p.url
                    except Exception:  # noqa: BLE001 - tab may be mid-close
                        continue
                    if url.startswith("https://shopee.com.br") and not _is_login_flow_url(url):
                        detected = p
                        break
                if detected is not None:
                    break
                if time.monotonic() - last_report >= 10:
                    urls = [p.url for p in context.pages]
                    print(f"aguardando login... abas abertas: {urls}", flush=True)
                    last_report = time.monotonic()
                    try:
                        context.pages[0].screenshot(path=str(settings.data_dir / "login_wait.png"))
                    except Exception:  # noqa: BLE001 - debug artifact only
                        pass
                time.sleep(1)
            if detected is None:
                raise TimeoutError(f"login not completed within {timeout_sec}s")
            print(f"login detectado em: {detected.url}", flush=True)
            detected.wait_for_timeout(3000)  # let session cookies settle
            context.storage_state(path=str(settings.shopee_auth_path))
        finally:
            browser.close()
    return settings.shopee_auth_path


# ---------------------------------------------------------------------------
# Browser scraping
# ---------------------------------------------------------------------------


def _extract_products(page: Page, seen: dict[int, ScrapedProduct]) -> None:
    for anchor in page.evaluate(_ANCHOR_DUMP_JS):
        parsed = parse_item_href(anchor["href"])
        if not parsed:
            continue
        shop_id, item_id = parsed
        if item_id in seen:
            continue
        title, price_cents, sold, rating = parse_card_text(anchor["text"])
        if not title or price_cents is None:
            continue
        seen[item_id] = ScrapedProduct(
            item_id=item_id,
            shop_id=shop_id,
            title=title,
            url=anchor["href"].split("?")[0],
            price_cents=price_cents,
            sold_count=sold or 0,
            rating=rating,
            image_url=anchor["img"],
        )


def _parse_network_items(response: Response) -> list[ScrapedProduct]:
    """Parse intercepted Shopee API JSON into ScrapedProduct."""
    if not ("/api/v4/search/search_items" in response.url or "/api/v4/recommend/" in response.url):
        return []

    try:
        data = response.json()
    except Exception:
        return []

    items = data.get("items") or data.get("data", {}).get("sections", [{}])[0].get("data", {}).get(
        "item", []
    )
    if not items:
        return []

    products = []
    for item in items:
        try:
            item_basic = item.get("item_basic") or item
            if not item_basic:
                continue

            itemid = int(item_basic.get("itemid", 0))
            shopid = int(item_basic.get("shopid", 0))
            if not itemid or not shopid:
                continue

            name = item_basic.get("name", "")
            price = item_basic.get("price")
            if price is None:
                continue
            price_cents = price // 100000

            sold_count = item_basic.get("historical_sold", 0)
            rating = item_basic.get("item_rating", {}).get("rating_star")

            img_id = item_basic.get("image", "")
            image_url = f"https://down-br.img.susercontent.com/file/{img_id}" if img_id else ""

            # create url from name
            safe_name = re.sub(r"[^a-zA-Z0-9-]", "-", name.lower())
            url = f"https://shopee.com.br/{safe_name}-i.{shopid}.{itemid}"

            products.append(
                ScrapedProduct(
                    item_id=itemid,
                    shop_id=shopid,
                    title=name,
                    url=url,
                    price_cents=price_cents,
                    sold_count=sold_count,
                    rating=rating,
                    image_url=image_url,
                )
            )
        except Exception as e:
            log.warning("Error parsing network item: %s", e)
            continue

    return products


def page_url(url: str, page_num: int) -> str:
    """Add/replace the `page=N` query param (Shopee search pagination)."""
    if "page=" in url:
        return re.sub(r"page=\d+", f"page={page_num}", url)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}page={page_num}"


MAX_PAGES = 20  # safety cap (~60 products/page -> 1200)


def scrape_best_sellers(
    max_products: int | None = None,
    *,
    dry_run: bool = False,
    category_url: str | None = None,
    screenshot_dir: Path | None = None,
) -> list[ScrapedProduct]:
    """Scrape Shopee BR camisetas sorted by sales. Returns up to `target` products.

    Pagination (verified 2026-07): infinite scroll caps out early, results
    continue via `?page=N` URLs. Strategy: scroll each page until stagnant,
    then advance to the next page."""
    settings = get_settings()
    if not settings.shopee_auth_path.exists():
        raise ShopeeAuthError(
            f"auth state not found at {settings.shopee_auth_path} - "
            "run `python -m agents.trend_scout.scraper --login` first"
        )
    target = 5 if dry_run else (max_products or settings.scrape_max_products)

    keywords = settings.scrape_keywords if not category_url else []
    urls_to_scrape = [category_url] if category_url else [search_url(kw) for kw in keywords]

    shots = screenshot_dir or settings.data_dir

    seen: dict[int, ScrapedProduct] = {}

    with sync_playwright() as pw:
        browser, context = _new_context(pw, headless=settings.scrape_headless, with_auth=True)
        try:
            page = context.new_page()

            network_items_captured = 0

            def _handle_response(response: Response):
                nonlocal network_items_captured
                try:
                    prods = _parse_network_items(response)
                    for p in prods:
                        if p.item_id not in seen:
                            seen[p.item_id] = p
                            network_items_captured += 1
                except Exception:
                    pass

            page.on("response", _handle_response)

            try:
                # warmup: enter via the home page (more human than cold search nav)
                page.goto("https://shopee.com.br/", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(random.randint(2500, 4500))

                for url in urls_to_scrape:
                    if len(seen) >= target:
                        break

                    stagnant_pages = 0
                    page_num = 0
                    new_since_pause = 0

                    while len(seen) < target and stagnant_pages < 2 and page_num < MAX_PAGES:
                        page.goto(
                            page_url(url, page_num), wait_until="domcontentloaded", timeout=60000
                        )
                        page.wait_for_timeout(random.randint(3000, 5000))
                        if page_num == 0:
                            _dismiss_overlays(page)
                        if _is_auth_wall(page.url):
                            raise ShopeeAuthError(
                                f"session expired or rejected (landed on {page.url}) - "
                                "re-run `python -m agents.trend_scout.scraper --login`"
                            )
                        if _is_captcha_wall(page.url):
                            raise ShopeeAuthError(
                                f"anti-bot captcha challenge at page {page_num} ({page.url}) - "
                                "re-run `python -m agents.trend_scout.scraper --login` "
                                "and solve the puzzle in the browser"
                            )

                        before = len(seen)
                        stagnant_scrolls = 0
                        network_items_before = network_items_captured

                        while len(seen) < target and stagnant_scrolls < 3:
                            prev = len(seen)

                            # Humanized scrolling jitter
                            scroll_amount = random.randint(1800, 3200)
                            scroll_steps = random.randint(3, 7)
                            for _ in range(scroll_steps):
                                page.mouse.wheel(0, scroll_amount // scroll_steps)
                                page.wait_for_timeout(random.randint(100, 300))

                            page.wait_for_timeout(random.randint(1200, 2500))

                            stagnant_scrolls = stagnant_scrolls + 1 if len(seen) == prev else 0
                            new_since_pause += max(0, len(seen) - prev)
                            if new_since_pause >= 25:
                                time.sleep(random.uniform(8, 12))  # politeness pause
                                new_since_pause = 0
                            else:
                                time.sleep(
                                    random.uniform(
                                        settings.scrape_delay_min_sec,
                                        settings.scrape_delay_max_sec,
                                    )
                                )

                        # Seamless DOM fallback
                        if network_items_captured == network_items_before:
                            _extract_products(page, seen)

                        stagnant_pages = stagnant_pages + 1 if len(seen) == before else 0
                        log.info("scrape page %d done: %d products total", page_num, len(seen))
                        page_num += 1

            except Exception:
                shots.mkdir(parents=True, exist_ok=True)
                ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                try:
                    page.screenshot(path=str(shots / f"scrape_error_{ts}.png"))
                finally:
                    raise
        finally:
            browser.close()

    return list(seen.values())[:target]


def main() -> int:
    parser = argparse.ArgumentParser(description="Shopee BR camisetas best-sellers scraper")
    parser.add_argument("--login", action="store_true", help="one-time manual login; saves session")
    parser.add_argument("--dry-run", action="store_true", help="fetch only 5 products")
    parser.add_argument("--max", type=int, default=None, help="max products (default: config)")
    parser.add_argument("--url", default=None, help="override category/search URL")
    args = parser.parse_args()

    if args.login:
        path = login()
        print(f"Session saved to {path}")
        return 0

    products = scrape_best_sellers(
        max_products=args.max, dry_run=args.dry_run, category_url=args.url
    )
    for p in products:
        brl = p.price_cents / 100
        print(f"{brl:>8.2f} BRL | {p.sold_count:>6} sold | {p.title[:70]} | {p.url}")
    print(f"\n{len(products)} products scraped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
