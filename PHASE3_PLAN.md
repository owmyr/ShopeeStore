# Phase 3 Plan — printed-shirts focus + design-ready references

## Goal
1. Stop wasting trend analysis on plain/lisa/basica/dry-fit shirts (useless to a print store).
2. Restructure the reference folder so the design agent gets clean per-theme visual inspiration.
3. Keep raw data auditability (plains persist in DB, never in trends/references).

## Decisions (locked with user)
- Search keyword default: `camiseta estampada` (config `SCRAPE_KEYWORD`).
- Reference layout: theme-segregated `data/reference/<theme-slug>/<item_id>.jpg`.
- LLM defense: clustering prompt gains a `nao-estampada` bucket; analyzer drops it from themes.
- Plains: kept in DB (`product`/`price_snapshot`), excluded from `TrendReport`, `report.json`, references.

## Print filter rule (title regex, pure function)
- PLAIN hints: `lisa`, `basica`, `basic`, `dry fit`, `malha fria`, `canelada`, `gola alta`, `gola o`, `seamless`, `sem estampa`
- PRINT hints: `estampa(da)`, `bordada`, `tema(s)`, `personagem`, `anime`, `manga`, `kpop`, `meme`, `frase`, `engracada`, `logo`, `caveira`, `floral/flores`, `estilo americano`, `gotica`, `tie dye`, `camuflada`
- Print hint WINS if both present. No hint at all -> keep (LLM decides).

## Commit order
1. `feat(trend-scout): search keyword config ("camiseta estampada")`
2. `feat(trend-scout): print filter module (title regex) + tests`
3. `feat(trend-scout): analyzer excludes plains + LLM nao-estampada bucket`
4. `feat(image-harvester): theme-segregated data/reference/<theme>/`
5. `feat(pulse): spike detection filtered to printed shirts`
6. `feat(dashboard): printed/excluded metrics + theme-grouped gallery`
7. `docs: phase 3 - print filter, reference layout`
8. `chore: verify live run + harvest after estampada switch`

## Per-module changes
- `core/config.py` + `.env.example`: `scrape_keyword` (default `camiseta estampada`)
- `agents/trend_scout/scraper.py`: search URL from keyword (URL-quoted), keep `?page=N`
- `agents/trend_scout/filter.py` (new): `is_plain(title)`, `theme_slug(theme)`
- `agents/trend_scout/prompts.py`: `nao-estampada` instruction in `CLUSTER_SYSTEM`
- `agents/trend_scout/analyzer.py`: printed-only ranking/price-bands/themes; `printed_count`, `excluded_plain_count` on `TrendReport` + `report.json`
- `agents/image_harvester/agent.py`: write to `data/reference/<slug>/<item_id>.jpg`, skip plain + `nao-estampada`
- `agents/pulse/agent.py`: spikes only for printed (raw snapshots still persist all)
- `dashboard/app.py`: Printed vs Excluded metrics; gallery grouped by theme folder
- tests: `test_filter.py` new; analyzer/pulse/harvester tests updated
- docs: `README.md`, `AGENTS.md`, `.opencode/skills/*`

## Verification (commit 8)
- `python __main__.py run-now`: report shows low `excluded_plain_count` (estampada keyword biases source) and richer theme clusters (no 100+ basica blob)
- `python __main__.py harvest`: `data/reference/` has per-theme subfolders with real printed-shirt images
- `ruff check .` + `pytest` green before every commit

## Risks
- "camiseta estampada" may return fewer results (~150-250 vs 314). Acceptable: cleaner signal.
- Regex false positives -> print-wins rule + LLM bucket + live spot-check in c8.
- Stale `data/images/` (gitignored) left as-is; new harvests write `data/reference/`.

## Deferred (NOT phase 3)
- LLM vision classifier (qwen2.5-vl) to verify prints visually
- Theme velocity (needs 2+ weeks of snapshots)
- Design Brief Agent (next phase; this plan is its prerequisite)
