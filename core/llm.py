"""Local Ollama LLM wrapper.

Hard rules (see AGENTS.md):
- Local Ollama only. No cloud LLM calls.
- Model name always comes from config (LLM_MODEL), never hardcoded.
- Callers batch inputs themselves (max 25 titles/call for clustering).
"""

import json
import re
from typing import Any

import ollama

from core.config import get_settings

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
_JSON_SPAN_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


class LLMOutputError(RuntimeError):
    """Model returned unparseable output after all retries."""


def _get_client() -> ollama.Client:
    return ollama.Client(host=get_settings().llm_host)


def _message_content(resp: Any) -> str:
    """Duck-typed content extraction across ollama-python versions."""
    msg = resp.get("message") if isinstance(resp, dict) else getattr(resp, "message", None)
    if isinstance(msg, dict):
        return str(msg.get("content", ""))
    return str(getattr(msg, "content", ""))


def chat(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.2,
    client: Any | None = None,
) -> str:
    client = client or _get_client()
    kwargs: dict[str, Any] = {"options": {"temperature": temperature}}
    if json_mode:
        kwargs["format"] = "json"
    resp = client.chat(
        model=get_settings().llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        **kwargs,
    )
    return _message_content(resp)


def parse_json(raw: str) -> Any:
    """Parse JSON from model output, tolerating fences and prose wrapping."""
    text = _FENCE_RE.sub("", raw.strip()).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_SPAN_RE.search(text)
        if match:
            return json.loads(match.group(1))
        raise


def chat_json(
    system: str,
    user: str,
    *,
    retries: int = 1,
    temperature: float = 0.2,
    client: Any | None = None,
) -> Any:
    """Chat expecting strict JSON back. Retries once (default) with a stricter
    prompt on parse failure; raises LLMOutputError if still unparseable."""
    client = client or _get_client()
    attempt_user = user
    for attempt in range(retries + 1):
        raw = chat(system, attempt_user, json_mode=True, temperature=temperature, client=client)
        try:
            return parse_json(raw)
        except json.JSONDecodeError:
            if attempt >= retries:
                raise LLMOutputError(
                    f"unparseable JSON after {retries + 1} attempt(s): {raw[:200]!r}"
                ) from None
            attempt_user = f"{user}\n\nResponda SOMENTE com JSON valido. Nenhum texto fora do JSON."
    raise LLMOutputError("unreachable")


def _model_names(resp: Any) -> set[str]:
    models = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", [])
    names: set[str] = set()
    for m in models:
        if isinstance(m, dict):
            names.add(str(m.get("name") or m.get("model") or ""))
        else:
            names.add(str(getattr(m, "model", "") or getattr(m, "name", "")))
    names.discard("")
    return names


def ensure_model_available(client: Any | None = None) -> None:
    """Raise a helpful error if the configured model is not pulled locally."""
    client = client or _get_client()
    model = get_settings().llm_model
    names = _model_names(client.list())
    if model not in names:
        raise RuntimeError(
            f"Ollama model {model!r} not found locally (have: {sorted(names)}). "
            f"Run: ollama pull {model}"
        )
