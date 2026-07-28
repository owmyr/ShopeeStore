---
name: shopee-br-scraping
description: Shopee Brazil (shopee.com.br) Playwright scraping patterns - category URLs, "Mais Vendidos" sorting, infinite-scroll pagination, anti-bot politeness, pt-BR price parsing. Use ONLY when working on agents/trend_scout/scraper.py or other Shopee BR scraping code.
---

# Shopee BR scraping

## Auth (HARD REQUIREMENT - verified 2026-07)
- Anonymous scraping hits a login wall: search/category URLs redirect to
  `shopee.com.br/verify/traffic/error` ("Login Necessario") for unauthenticated
  sessions, even with clean fingerprint + delays.
- Solution: one-time manual login via headed Playwright
  (`python -m agents.trend_scout.scraper --login`), session persisted with
  `context.storage_state()` to `SHOPEE_AUTH_PATH` (default
  `data/shopee_auth.json`, gitignored - NEVER commit it).
- All scrape runs load `storage_state` from that file.
- Detect expiry: after EVERY page `goto`, check walls. Two distinct walls:
  - `/verify/traffic` or `/buyer/login` -> session expired/rejected
  - `/verify/captcha` -> anti-bot slider challenge (session flagged after
    heavy scraping; user solves puzzle in headed --login window)
  Both -> screenshot + raise `ShopeeAuthError`. Never silently scrape zero.
- Warmup: navigate to the home page FIRST, wait 2.5-4.5s, then go to the
  search URL. Cold direct-to-search navigation is a bot signal.

## Search keyword (phase 3)
- Default keyword is `camiseta estampada` (config `SCRAPE_KEYWORD`) - biases
  results toward PRINTED shirts at the source, which is what we sell.
- URL: `https://shopee.com.br/search?keyword=<quoted>&sortBy=sales`.

## Category URL
- Format: `https://shopee.com.br/{slug}-cat.{shopid}.{categoryid}`
- Category IDs are NOT stable across documentation; resolve the exact
  camisetas URL at dev time (navigate shopee.com.br manually), then pin it in
  `.env` as `SCRAPE_CATEGORY_URL`. Never hardcode a guessed ID.
- Sort by best sellers: append `?sortBy=sales`.

## Pagination (updated 2026-07 after live run)
- Infinite scroll CAPS OUT early (only ~38 products extractable by scrolling).
- Results continue via explicit `?page=N` query param (0-indexed); the
  pagination links appear in the DOM (`/search?...&page=1`).
- Strategy: scroll each page until stagnant (~3 rounds), then
  `goto(page_url(base, N))`. ~60 products per page. Cap at MAX_PAGES=20.

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
