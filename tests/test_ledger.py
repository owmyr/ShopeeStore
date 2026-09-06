"""Ledger tests."""

import json

import pytest
from sqlmodel import select

from core import db, ledger
from core.models import AgentLedger


def _all_runs() -> list[AgentLedger]:
    with db.session_scope() as s:
        return list(s.exec(select(AgentLedger)).all())


def test_successful_run_is_recorded_in_db_and_jsonl(isolated, tmp_path) -> None:
    with ledger.run("trend_scout", inputs={"max_products": 5}) as handle:
        handle.set_outputs("data/reports/x/")

    runs = _all_runs()
    assert len(runs) == 1
    rec = runs[0]
    assert rec.agent == "trend_scout"
    assert rec.status == "success"
    assert rec.ended_at is not None
    assert rec.duration_sec is not None and rec.duration_sec >= 0
    assert rec.outputs_path == "data/reports/x/"
    assert rec.error == ""

    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["run_id"] == rec.run_id
    assert entry["status"] == "success"
    assert entry["outputs_path"] == "data/reports/x/"


def test_failed_run_is_recorded_and_reraised(isolated, tmp_path) -> None:
    with pytest.raises(ValueError, match="boom"):
        with ledger.run("trend_scout", inputs={}):
            raise ValueError("boom")

    runs = _all_runs()
    assert len(runs) == 1
    assert runs[0].status == "error"
    assert "ValueError: boom" in runs[0].error

    entry = json.loads((tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip())
    assert entry["status"] == "error"
    assert "boom" in entry["error"]


def test_inputs_hash_is_order_insensitive(isolated) -> None:
    h1 = ledger.hash_inputs({"b": 2, "a": 1})
    h2 = ledger.hash_inputs({"a": 1, "b": 2})
    assert h1 == h2


def test_last_successful_run_matches_inputs(isolated) -> None:
    with ledger.run("trend_scout", inputs={"max_products": 500}):
        pass
    with ledger.run("trend_scout", inputs={"max_products": 5}):
        pass

    found = ledger.last_successful_run("trend_scout", {"max_products": 500})
    assert found is not None
    assert found.status == "success"

    assert ledger.last_successful_run("trend_scout", {"max_products": 999}) is None
    assert ledger.last_successful_run("other_agent", {"max_products": 500}) is None
