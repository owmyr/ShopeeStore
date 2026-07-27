# ShopeeStore

Shopee BR camisetas trend intelligence: weekly best-seller scrape (authenticated),
local-LLM theme clustering, Streamlit supervision dashboard.

**Status: MVP complete** — Trend Scout agent end-to-end. Deferred: design brief,
supplier comms, listing agents.

## Requirements

- Windows, Python 3.11+
- [Ollama](https://ollama.com) running locally
- Google Chrome installed (used for the one-time Shopee login)
- A Shopee account (email/password — Google OAuth blocks automated browsers)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
copy .env.example .env
ollama pull qwen2.5:14b-instruct
```

## One-time Shopee login

Anonymous scraping is blocked by a login wall. Do this once (and again whenever
the session expires):

```powershell
python __main__.py login
```

A Chrome window opens. Log in; the script detects it and saves the session to
`data/shopee_auth.json` (gitignored — never commit it).

## Usage

```powershell
python __main__.py dashboard   # supervision UI (ledger, trends, gallery, run-now)
python __main__.py run         # run Trend Scout once (skips if run <24h ago)
python __main__.py run-now     # force a run now
python __main__.py harvest     # download top product images (data/images/)
python __main__.py pulse       # daily spike radar (top 20 + new/jump detection)
python __main__.py schedule    # in-app scheduler (dev; see below for unattended)
```

Dev scraper (no DB/LLM): `python -m agents.trend_scout.scraper --dry-run`

## Unattended runs (Windows Task Scheduler)

```powershell
powershell -File scripts\install_tasks.ps1    # register (idempotent)
powershell -File scripts\uninstall_tasks.ps1  # remove
```

Registers `ShopeeStore-WeeklyRun` (Mon 09:00: deep scrape + report + image
harvest) and `ShopeeStore-DailyPulse` (daily 08:30: spike radar). Tasks run
only while you are logged on; `StartWhenAvailable` catches up missed runs.

## How it works

1. **Scrape** (`agents/trend_scout/scraper.py`) — Playwright, search "camiseta"
   sorted by sales, infinite scroll, polite jittered delays, screenshot-on-error.
2. **Analyze** (`agents/trend_scout/analyzer.py`) — dedupe, rank by sold count,
   price-band percentiles, theme clustering via local Ollama (max 25 titles/call).
3. **Report** (`agents/trend_scout/agent.py`) — SQLite snapshots +
   `data/reports/<ts>/{report.md,report.json,prices.png,themes.png}`.
4. **Supervise** (`dashboard/app.py`) — every run is logged to the agent ledger
   (`agent_ledger` table + `data/ledger.jsonl`).

## Tests & lint

```powershell
ruff check .
pytest
```

## Troubleshooting

- **`ShopeeAuthError`** — session expired; run `python __main__.py login` again.
- **Ollama model not found** — `ollama pull qwen2.5:14b-instruct` (or set
  `LLM_MODEL` in `.env` to a model you have).
- **Scrape returns few/no products** — check `data/*.png` error screenshots and
  `data/agent_run_now.log`; anti-bot challenges usually mean re-login.
