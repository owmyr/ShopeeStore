"""Dashboard smoke test (Streamlit AppTest - no browser)."""

from collections.abc import Iterator

import pytest
from streamlit.testing.v1 import AppTest

from core import db
from core.config import get_settings


@pytest.fixture()
def isolated(tmp_path, monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    get_settings.cache_clear()
    db.reset_engine()
    yield
    db.reset_engine()
    get_settings.cache_clear()


def test_app_runs_without_exceptions(isolated) -> None:
    at = AppTest.from_file("dashboard/app.py", default_timeout=60)
    at.run()
    assert not at.exception
