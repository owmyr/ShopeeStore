"""Local Ollama LLM wrapper.

Hard rules (see AGENTS.md):
- Local Ollama only. No cloud LLM calls.
- Model name always comes from config (LLM_MODEL), never hardcoded.
- Callers batch inputs themselves (max 25 titles/call for clustering).
"""

import json
import logging
import random
import re
import time
from typing import Any

import ollama
from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

from core.config import get_settings

log = logging.getLogger(__name__)

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


def _chat_json_gemini(
    system: str,
    user: str,
    *,
    response_model: type[BaseModel] | None = None,
    temperature: float = 0.2,
) -> Any:
    """Uses Gemini models with quota failover and structured outputs."""
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ValueError("gemini_api_key not configured")

    client = genai.Client(api_key=settings.gemini_api_key)

    config_kwargs: dict[str, Any] = {
        "temperature": temperature,
        "response_mime_type": "application/json",
        "system_instruction": system,
    }
    if response_model:
        config_kwargs["response_schema"] = response_model

    for model_name in settings.gemini_model_pool:
        for attempt in range(settings.gemini_max_retries_503 + 1):
            try:
                config = genai_types.GenerateContentConfig(**config_kwargs)
                resp = client.models.generate_content(
                    model=model_name, contents=user, config=config
                )
                if not resp.text:
                    raise ValueError("Empty response text")
                return json.loads(resp.text)
            except Exception as exc:
                err_str = str(exc)
                if "503" in err_str or "UNAVAILABLE" in err_str or "high demand" in err_str.lower():
                    if attempt < settings.gemini_max_retries_503:
                        delay = settings.gemini_retry_delay_sec * (1.5**attempt) + random.uniform(
                            0.5, 2.0
                        )
                        log.warning(
                            (
                                "Gemini model %s busy (503). Retrying in %.1fs (attempt %d/%d) "
                                "to preserve top-tier quality..."
                            ),
                            model_name,
                            delay,
                            attempt + 1,
                            settings.gemini_max_retries_503,
                        )
                        time.sleep(delay)
                        continue
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    log.warning(
                        (
                            "Gemini model %s quota exhausted (429). "
                            "Rolling over to next model in pool..."
                        ),
                        model_name,
                    )
                    break
                log.warning("Gemini model %s error: %s. Rolling over...", model_name, exc)
                break
    raise LLMOutputError("All Gemini models failed")


def chat_json(
    system: str,
    user: str,
    *,
    retries: int = 1,
    temperature: float = 0.2,
    client: Any | None = None,
    response_model: type[BaseModel] | None = None,
) -> Any:
    """Chat expecting strict JSON back. Retries once (default) with a stricter
    prompt on parse failure; raises LLMOutputError if still unparseable."""
    settings = get_settings()
    if settings.llm_provider == "gemini" and settings.gemini_api_key and genai is not None:
        try:
            return _chat_json_gemini(
                system=system,
                user=user,
                response_model=response_model,
                temperature=temperature,
            )
        except (LLMOutputError, ValueError) as exc:
            log.warning("Gemini failed: %s. Falling back to Ollama...", exc)

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
