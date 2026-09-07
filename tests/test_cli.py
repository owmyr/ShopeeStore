"""CLI entrypoint tests."""

import importlib.util
import subprocess
import sys

import pytest


def _load_cli():
    spec = importlib.util.spec_from_file_location("shopee_store_cli", "__main__.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_help_exits_zero() -> None:
    result = subprocess.run(
        [sys.executable, "__main__.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "dashboard" in result.stdout


@pytest.mark.parametrize(
    ("command", "expected_force"),
    [("run", False), ("run-now", True)],
)
def test_run_dispatch(monkeypatch, command, expected_force) -> None:
    calls: list = []

    def fake_run_once(*, force=False, **kwargs):
        calls.append(force)
        return None

    monkeypatch.setattr("agents.trend_scout.agent.run_once", fake_run_once)
    monkeypatch.setattr(sys, "argv", ["shopee-store", command])

    cli = _load_cli()
    assert cli.main() == 0
    assert calls == [expected_force]


def test_export_web_dispatch(monkeypatch, tmp_path) -> None:
    calls: list = []

    def fake_export(*, report_dir=None, output_dir=None):
        calls.append(report_dir)
        return tmp_path / "client_report.json"

    monkeypatch.setattr("core.exporter.export_client_report", fake_export)
    monkeypatch.setattr(sys, "argv", ["shopee-store", "export-web", "--report-dir", str(tmp_path)])

    cli = _load_cli()
    assert cli.main() == 0
    assert len(calls) == 1
    assert str(calls[0]) == str(tmp_path)
