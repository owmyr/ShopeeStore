# AGENTS.md


# CRITICAL RULES - MUST FOLLOW

## RESPONSES
- Keep responses concise and to the point - unless the user asks otherwise

## PLANNING MODE
- Ask clarifying questions only when requirements are ambiguous
- Never assume design, tech stack or features
- Use deep-dive sub-agents to assist with research
- Use deep-dive sub-agents to review the different aspects of your plan before presenting to the user

## CHANGE / EDIT MODE
- Never implement features yourself when possible - use sub-agents!
- Identify changes from the plan that can be implemented in parallel, and use sub-agents to implement the features efficiently
- When using sub-agents to implement features, act as a coordinator only
- Use the best model for the task - premium models for complex tasks (like coding) and mid-tier models for simpler tasks, like documentation
- For Python changes, run `ruff check .` and `pytest`; also run a configured type checker when one exists.

## TESTING

- Use any testing tools, libraries available to the project for testing your changes
- Never assume your changes simply work, always test!
- If the project does not have any testing tools, scripts, MCP tools, skills, etc. available for testing, ask the user whether testing should be skipped.

## Project
Shopee BR camisetas trend intelligence & B2B merchant outreach ecosystem.
Weekly scrape of Shopee Brazil best-sellers (camisetas category), adaptive seed discovery,
LLM-assisted clustering (Gemini API with Ollama fallback), weekly executive dossier generation (PDF/PNG),
automated Shopee Chat outreach, and an air-gapped subscriber portal on Next.js/Vercel.

## Layout
- `core/` - config, db, models, ledger, llm (Gemini/Ollama), exporter, scheduler (shared infrastructure)
- `agents/trend_scout/` - scraper, analyzer, agent orchestration, adaptive seeds, prompts, filter (print detection)
- `agents/image_harvester/` - downloads printed-shirt reference images into `data/reference/<theme>/`
- `agents/pulse/` - daily top-20 scrape + spike detection (lightweight, printed only)
- `agents/dossier/` - compiles weekly executive intelligence dossier (multi-page PDF & high-res PNG) via Playwright & Jinja2
- `agents/lead_scout/` - discovers & enriches merchant store leads (CNPJ, BrasilAPI, Instagram handles, niche classification)
- `agents/outreach/` - automates Shopee Chat messaging with attached `dossier.png`, typing jitter, and anti-ban safeguards
- `web/` - Next.js (App Router), TypeScript, Tailwind CSS client portal deployed to Vercel (air-gapped via `client_report.json`)
- `dashboard/` - Streamlit supervision UI & CRM management hub
- `agents/` is the Python application package; it is not a skills directory.
- `.opencode/skills/` - curated OpenCode-only project skills for this repository
- `.agents/skills/` - external skills managed by the `npx skills` CLI
- `skills-lock.json` - lockfile for skills installed by the Skills CLI
- `scripts/` - Windows Task Scheduler install/uninstall
- `tests/` - pytest test suite (221 tests)
- `data/` - gitignored: sqlite db, reports, ledger jsonl, reference images, error screenshots, shopee_auth.json

## Skill installation
- OpenCode discovers both `.opencode/skills/` and `.agents/skills/`.
- Keep repository-specific, OpenCode-only guidance in `.opencode/skills/`.
- Keep downloaded or cross-agent skills in `.agents/skills/`; do not duplicate them in `.opencode/skills/`.
- New project skills installed by `npx skills add` belong in `.agents/skills/`. Use `--agent opencode --yes` when the skill is only for OpenCode.
- Keep `skills-lock.json` with the project so installs can be restored consistently.

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
- LLM: Google Gemini API (`GEMINI_API_KEY` with model pool) with local Ollama fallback (`Qwen2.5:14b`).
- LLM batching: max 25 product titles per call for JSON structure discipline.
- Scraping: polite delays 3-6s/page with jitter; pause every 25 items;
  screenshot to `data/` on error; `--dry-run` flag (5 products) for dev.
- Shopee auth: anonymous scraping is blocked (login wall). Session lives in
  `SHOPEE_AUTH_PATH` (gitignored); refresh via
  `python -m agents.trend_scout.scraper --login`. Never commit auth state.
- Observability: every agent run must log to the ledger (`core/ledger.py`) -
  agent name, start/end, inputs hash, outputs path, status, error.
- Credentials: No secrets in code; use `.env` (copy from `.env.example`).
- All money values stored as integer cents (BRL). Prices parsed from
  pt-BR format ("1.234,56").
