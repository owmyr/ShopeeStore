"""LLM wrapper tests (mocked Ollama client - no daemon needed)."""

import pytest

from core import llm


class FakeClient:
    def __init__(self, responses: list[str], models: list[str] | None = None) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        self._models = models if models is not None else ["qwen2.5:14b-instruct"]

    def chat(self, model, messages, **kwargs):
        self.calls.append({"model": model, "messages": messages, **kwargs})
        return {"message": {"content": self.responses.pop(0)}}

    def list(self):
        return {"models": [{"name": n} for n in self._models]}


def test_chat_uses_configured_model_and_json_format() -> None:
    client = FakeClient(['{"ok": true}'])
    out = llm.chat("sys", "user", json_mode=True, client=client)
    assert out == '{"ok": true}'
    call = client.calls[0]
    assert call["model"] == "qwen2.5:14b-instruct"
    assert call["format"] == "json"
    assert call["messages"][0] == {"role": "system", "content": "sys"}


def test_parse_json_plain() -> None:
    assert llm.parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_strips_markdown_fences() -> None:
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('```\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_extracts_span_from_prose() -> None:
    raw = 'Aqui esta o resultado: {"clusters": []} espero ter ajudado'
    assert llm.parse_json(raw) == {"clusters": []}


def test_parse_json_raises_on_garbage() -> None:
    with pytest.raises(Exception):  # noqa: B017 - json.JSONDecodeError subclass
        llm.parse_json("definitely not json")


def test_chat_json_success_first_try() -> None:
    client = FakeClient(['{"clusters": [{"theme": "memes", "indices": [1]}]}'])
    out = llm.chat_json("sys", "user", client=client)
    assert out["clusters"][0]["theme"] == "memes"
    assert len(client.calls) == 1


def test_chat_json_retries_once_with_stricter_prompt() -> None:
    client = FakeClient(["lixo total", '{"ok": 1}'])
    out = llm.chat_json("sys", "user", client=client)
    assert out == {"ok": 1}
    assert len(client.calls) == 2
    second_user = client.calls[1]["messages"][1]["content"]
    assert "SOMENTE" in second_user


def test_chat_json_raises_after_retries_exhausted() -> None:
    client = FakeClient(["lixo", "ainda lixo"])
    with pytest.raises(llm.LLMOutputError):
        llm.chat_json("sys", "user", retries=1, client=client)
    assert len(client.calls) == 2


def test_ensure_model_available_ok() -> None:
    client = FakeClient([], models=["qwen2.5:14b-instruct", "llama3.2:1b"])
    llm.ensure_model_available(client=client)  # no raise


def test_ensure_model_available_missing() -> None:
    client = FakeClient([], models=["llama3.2:1b"])
    with pytest.raises(RuntimeError, match="ollama pull"):
        llm.ensure_model_available(client=client)
