import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from core import db
from core.config import get_settings


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Provide an isolated environment for tests with a temporary database and data directory."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield tmp_path
    db.reset_engine()
    get_settings.cache_clear()


class FakeLLM:
    """Unified test fake for local Ollama client."""

    def __init__(self, responses: list[str] | None = None) -> None:
        """Initialize with a list of responses to pop from."""
        self.responses = list(responses) if responses is not None else None
        self.user_prompts: list[str] = []

    def chat(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        """Mock the chat method to return a predefined response or default JSON."""
        if len(messages) > 1 and isinstance(messages[1], dict) and "content" in messages[1]:
            self.user_prompts.append(messages[1]["content"])
        if self.responses is not None and len(self.responses) > 0:
            content = self.responses.pop(0)
        else:
            content = json.dumps({"clusters": []})
        return {"message": {"content": content}}
