---
name: agent-ledger-pattern
description: Agent observability ledger pattern - every agent run logs name/start/end/inputs_hash/outputs_path/status/error to SQLite plus a JSONL audit trail. Use ONLY when working on core/ledger.py, core/models.py, or agent orchestration code (agents/*/agent.py).
---

# Agent ledger pattern

Every agent run MUST be recorded. This is the user's supervision surface.

## Schema (SQLite table `agent_ledger` + JSONL `data/ledger.jsonl`)
- `run_id`: uuid4 string
- `agent`: agent name (e.g. "trend_scout")
- `started_at`, `ended_at`: UTC ISO-8601 (ended_at null while running)
- `status`: "running" | "success" | "error"
- `inputs_hash`: sha256 hex of normalized inputs (sorted JSON dump)
- `outputs_path`: path to the main artifact (report dir/file) or null
- `error`: traceback/message string or null
- `duration_sec`: float, computed on close

## Usage contract (context manager)
```python
with ledger.run("trend_scout", inputs={"max_products": 500}) as run:
    ...
    run.set_outputs("data/reports/2026-07-27/")
# on normal exit: status=success; on exception: status=error + re-raise
```

## Rules
- Dual-write: insert row in SQLite AND append one JSON object per line to
  the JSONL file (same content, JSONL is the human-greppable audit trail).
- The context manager NEVER swallows exceptions - record then re-raise.
- `inputs_hash` makes runs idempotency-checkable: agents compare the hash
  against the last successful run to skip redundant work.
- All timestamps UTC; format in pt-BR only at the dashboard layer.
