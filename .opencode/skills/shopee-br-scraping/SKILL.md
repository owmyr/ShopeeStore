---
name: shopee-br-scraping
description: Shopee Brazil (shopee.com.br) Playwright scraping patterns - category URLs, "Mais Vendidos" sorting, infinite-scroll pagination, anti-bot politeness, pt-BR price parsing. Use ONLY when working on agents/trend_scout/scraper.py or other Shopee BR scraping code.
---

# Shopee BR scraping

## Category URL
- Format: `https://shopee.com.br/{slug}-cat.{shopid}.{categoryid}`
- Category IDs are NOT stable across documentation; resolve the exact
  camisetas URL at dev time (navigate shopee.com.br manually), then pin it in
  `.env` as `SCRAPE_CATEGORY_URL`. Never hardcode a guessed ID.
- Sort by best sellers: append `?sortBy=sales`.

## Pagination
- Infinite scroll: no "next page" link. Drive it with
  `page.mouse.wheel(0, ~2500)` + `page.wait_for_timeout(1500)` in a loop until
  the product count stops growing or `SCRAPE_MAX_PRODUCTS` is reached.
- ~60 items load per scroll batch.

## Extraction
- Product anchors match the pattern `/{name}-i.{shopid}.{itemid}` - extract
  `itemid`/`shopid` via regex on `href` (dedupe key).
- Avoid generated class names (they churn). Prefer stable attributes and
  anchor-href parsing; fall back to card-level text extraction.
- Prices are pt-BR formatted: `R$ 1.234,56`. Parse to integer cents
  (strip "R$", dots are thousands separators, comma is decimal).
- Sales counts appear as "1,2 mil vendidos" / "10 mil+ vendidos" /
  "50 vendidos". Parse `mil` = x1000, `+` = floor, comma decimal.
- Ratings appear as "4,8" near a star; may be absent for low-review items.

## Anti-bot politeness (hard rules)
- One browser context per run. Viewport 1366x768, locale `pt-BR`,
  timezone `America/Sao_Paulo`, realistic desktop UA.
- Delay `SCRAPE_DELAY_MIN_SEC`..`SCRAPE_DELAY_MAX_SEC` (3-6s) with random
  jitter between scroll batches; extra ~10s pause every 25 items.
- On any error or suspected challenge: `page.screenshot()` to `data/` with a
  timestamped name BEFORE raising.
- `--dry-run` flag caps at 5 products for development.
- Playwright chromium only (installed via `playwright install chromium`).
