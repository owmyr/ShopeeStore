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
Shopee BR camisetas trend intelligence. Weekly scrape of Shopee Brazil best-sellers
(camisetas category), LLM-assisted trend clustering, Streamlit supervision dashboard.
Agents: Trend Scout (MVP). Design brief, supplier comms, listing agents deferred.

## Layout
- `core/` - config, db, models, ledger, llm, scheduler (shared infrastructure)
- `agents/trend_scout/` - scraper, analyzer, agent orchestration, prompts, filter (print detection)
- `agents/image_harvester/` - downloads printed-shirt images into `data/reference/<theme>/`
- `agents/pulse/` - daily top-20 scrape + spike detection (no LLM, printed only)
- `agents/` is the Python application package; it is not a skills directory.
- `.opencode/skills/` - curated OpenCode-only project skills for this repository
- `.agents/skills/` - external skills managed by the `npx skills` CLI
- `skills-lock.json` - lockfile for skills installed by the Skills CLI
- `dashboard/` - Streamlit supervision UI
- `scripts/` - Windows Task Scheduler install/uninstall
- `tests/` - pytest
- `data/` - gitignored: sqlite db, reports, ledger jsonl, reference images, error screenshots

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
