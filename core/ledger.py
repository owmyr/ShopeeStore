"""Agent run ledger (observability).

Every agent run is recorded: SQLite row (queryable) + one JSON line appended
to the JSONL audit trail (human-greppable). Exceptions are recorded, then
re-raised - the ledger never swallows failures.
"""

import hashlib
import json
import traceback
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlmodel import select

from core.config import get_settings
from core.db import session_scope
from core.models import AgentLedger


def hash_inputs(inputs: dict[str, Any]) -> str:
    payload = json.dumps(inputs, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


class RunHandle:
    """Mutable handle passed to the `with` body."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.outputs_path = ""

    def set_outputs(self, path: str) -> None:
        self.outputs_path = path


@contextmanager
def run(agent: str, inputs: dict[str, Any] | None = None) -> Iterator[RunHandle]:
    settings = get_settings()
    settings.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    run_id = uuid.uuid4().hex
    started = datetime.now(UTC)
    inputs_hash = hash_inputs(inputs or {})

    with session_scope() as s:
        s.add(
            AgentLedger(
                run_id=run_id,
                agent=agent,
                started_at=started,
                status="running",
                inputs_hash=inputs_hash,
            )
        )
        s.commit()

    handle = RunHandle(run_id)
    status = "success"
    error_text = ""
    try:
        yield handle
    except Exception:
        status = "error"
        error_text = traceback.format_exc()
        raise
    finally:
        ended = datetime.now(UTC)
        duration = (ended - started).total_seconds()

        with session_scope() as s:
            rec = s.get(AgentLedger, run_id)
            if rec is not None:
                rec.ended_at = ended
                rec.status = status
                rec.error = error_text
                rec.outputs_path = handle.outputs_path
                rec.duration_sec = duration
                s.add(rec)
                s.commit()

        line = json.dumps(
            {
                "run_id": run_id,
                "agent": agent,
                "started_at": started.isoformat(),
                "ended_at": ended.isoformat(),
                "status": status,
                "inputs_hash": inputs_hash,
                "outputs_path": handle.outputs_path,
                "error": error_text,
                "duration_sec": duration,
            }
        )
        with open(settings.ledger_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def last_successful_run(agent: str, inputs: dict[str, Any]) -> AgentLedger | None:
    """Return the most recent successful run of `agent` with identical inputs."""
    target_hash = hash_inputs(inputs)
    with session_scope() as s:
        stmt = (
            select(AgentLedger)
            .where(
                AgentLedger.agent == agent,
                AgentLedger.status == "success",
                AgentLedger.inputs_hash == target_hash,
            )
            .order_by(AgentLedger.started_at.desc())  # type: ignore[attr-defined]
        )
        return s.exec(stmt).first()
