"""Scheduler tests (agent run faked)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from agents.trend_scout import agent as trend_scout
from core import db, scheduler
from core.config import get_settings


@pytest.fixture()
def isolated(tmp_path, monkeypatch) -> Iterator:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEDGER_PATH", str(tmp_path / "l.jsonl"))
    get_settings.cache_clear()
    db.reset_engine()
    yield tmp_path
    db.reset_engine()
    get_settings.cache_clear()


def _fake_run(calls: list):
    def run() -> None:
        calls.append(1)

    return run


def test_self_heal_runs_when_never_run(isolated, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(trend_scout, "run_once", _fake_run(calls))
    assert scheduler.self_heal() is True
    assert len(calls) == 1
    assert scheduler.last_scheduled_run() is not None


def test_self_heal_skips_recent_run(isolated, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(trend_scout, "run_once", _fake_run(calls))
    scheduler._mark_last_run()
    assert scheduler.self_heal() is False
    assert calls == []


def test_self_heal_runs_when_stale(isolated, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(trend_scout, "run_once", _fake_run(calls))
    stale = datetime.now(UTC) - timedelta(days=8)
    (isolated / scheduler.LAST_RUN_FILE).write_text(stale.isoformat(), encoding="utf-8")
    assert scheduler.self_heal() is True
    assert len(calls) == 1


def test_build_scheduler_registers_weekly_job(isolated) -> None:
    s = scheduler.build_scheduler()
    job = s.get_job("trend_scout_weekly")
    assert job is not None
