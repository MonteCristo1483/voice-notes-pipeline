"""LLM providers: local Ollama and any OpenAI-compatible cloud API.

Both return a parsed JSON object. Cloud is preferred when configured; if it
fails twice, the pipeline falls back to the local model so a recording is never
lost because of the network.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Any

from .config import Settings
from .schemas import schema_example

log = logging.getLogger(__name__)

REASONING_PREFIXES = ("gpt-5", "gpt-6", "o3", "o4")


def parse_json_text(text: str | None) -> dict[str, Any]:
    """Parse model JSON, tolerating ```json fences."""
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Zа-яА-Я]*[ \t]*\n?", "", text)
    text = re.sub(r"\n?```[ \t]*$", "", text).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("model returned JSON that is not an object")
    return data


def local_json(
    settings: Settings,
    prompt: str,
    schema: dict[str, Any],
    system: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Structured output from Ollama with grammar-constrained JSON."""

    def call(fmt: Any) -> dict[str, Any]:
        payload = json.dumps(
            {
                "model": settings.local_model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "format": fmt,
                "options": {
                    "temperature": temperature,
                    "num_ctx": 8192,
                    "top_p": 0.9,
                    "repeat_penalty": 1.05,
                    # Small models occasionally loop inside a JSON string.
                    "num_predict": 1800,
                },
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            settings.ollama_url + "/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            raw = json.loads(response.read().decode("utf-8"))["response"]
        return parse_json_text(raw)

    last_error: Exception | None = None
    for attempt in (1, 2):
        try:
            return call(schema)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            last_error = exc
            log.warning("local model returned invalid JSON (%s), attempt %s/2", exc, attempt)
    raise RuntimeError(f"local model failed to produce JSON: {last_error}")


def cloud_json(
    settings: Settings,
    prompt: str,
    schema: dict[str, Any],
    system: str,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Structured output from an OpenAI-compatible endpoint (text only)."""
    hint = json.dumps(schema_example(schema), ensure_ascii=False)
    body: dict[str, Any] = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": prompt + "\n\nОтвет — строго JSON с такими полями (заполни значения):\n" + hint,
            },
        ],
        "stream": False,
    }
    if settings.llm_model.startswith(REASONING_PREFIXES):
        body["max_completion_tokens"] = 4000
    else:
        body["max_tokens"] = 4000
        body["temperature"] = temperature

    def call(json_mode: bool) -> dict[str, Any]:
        payload = dict(body)
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            settings.llm_api_base + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + settings.llm_api_key,
            },
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
        usage = data.get("usage") or {}
        if usage:
            log.info(
                "cloud tokens: %s in / %s out",
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        return parse_json_text(content)

    try:
        return call(True)
    except urllib.error.HTTPError as exc:
        if exc.code == 400:  # some gateways reject response_format
            return call(False)
        raise


def generate_json(
    settings: Settings,
    prompt: str,
    schema: dict[str, Any],
    system: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Cloud first (when configured), local fallback on any failure."""
    if settings.cloud_enabled:
        for attempt in (1, 2):
            try:
                return cloud_json(settings, prompt, schema, system, max(temperature, 0.3))
            except urllib.error.HTTPError as exc:
                if exc.code == 401:
                    log.error("cloud: key rejected (401)")
                elif exc.code == 402:
                    log.error("cloud: no balance (402)")
                elif exc.code == 429:
                    log.warning("cloud: rate limited (429)")
                else:
                    log.warning("cloud: HTTP %s", exc.code)
            except Exception as exc:  # noqa: BLE001 - fallback must be broad
                log.warning("cloud failed (%s), attempt %s/2", exc, attempt)
        log.warning("cloud unavailable — falling back to the local model")
    return local_json(settings, prompt, schema, system, temperature)
