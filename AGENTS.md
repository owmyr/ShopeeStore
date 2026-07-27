# AGENTS.md

## Project
Shopee BR camisetas trend intelligence. Weekly scrape of Shopee Brazil best-sellers
(camisetas category), LLM-assisted trend clustering, Streamlit supervision dashboard.
Agents: Trend Scout (MVP). Design brief, supplier comms, listing agents deferred.

## Layout
- `core/` - config, db, models, ledger, llm, scheduler (shared infrastructure)
- `agents/trend_scout/` - scraper, analyzer, agent orchestration, prompts, filter (print detection)
- `agents/image_harvester/` - downloads printed-shirt images into `data/reference/<theme>/`
- `agents/pulse/` - daily top-20 scrape + spike detection (no LLM, printed only)
- `dashboard/` - Streamlit supervision UI
- `scripts/` - Windows Task Scheduler install/uninstall
- `tests/` - pytest
- `data/` - gitignored: sqlite db, reports, ledger jsonl, reference images, error screenshots

## Print filter (phase 3 - core business rule)
- We sell PRINTED shirts. Plain/lisa/basica/dry-fit shirts are useless.
- `agents/trend_scout/filter.py` `is_plain(title)`: PLAIN regex marks printless;
  PRINT hints (estampada, bordada, anime, kpop, caveira, ...) always win.
- Plains stay in DB (audit) but are excluded from TrendReport, report.json,
  `data/reference/`, and pulse spikes. LLM may tag stragglers `nao-estampada`.
- Scrape keyword default is `camiseta estampada` (config `SCRAPE_KEYWORD`).

## Conventions
- Python 3.11+, `ruff check .` and `pytest` must pass before every commit.
- Conventional commits: `feat:`, `chore:`, `test:`, `docs:`, `fix:`, `refactor:`.
- LLM: local Ollama only. Model read from config (`LLM_MODEL`), never hardcoded.
- LLM batching: max 25 product titles per call (small-model JSON discipline).
- Scraping: polite delays 3-6s/page with jitter; pause every 25 items;
  screenshot to `data/` on error; `--dry-run` flag (5 products) for dev.
- Shopee auth: anonymous scraping is blocked (login wall). Session lives in
  `SHOPEE_AUTH_PATH` (gitignored); refresh via
  `python -m agents.trend_scout.scraper --login`. Never commit auth state.
- Observability: every agent run must log to the ledger (`core/ledger.py`) -
  agent name, start/end, inputs hash, outputs path, status, error.
- No cloud LLM calls. No secrets in code; use `.env` (copy from `.env.example`).
- All money values stored as integer cents (BRL). Prices parsed from
  pt-BR format ("1.234,56").
