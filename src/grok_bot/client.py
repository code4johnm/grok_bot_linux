"""HTTP client for the official xAI chat completions endpoint."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from grok_bot.config import Settings


class GrokAPIError(RuntimeError):
    """The xAI API returned an error or an unexpected payload."""


def extract_reply(payload: dict[str, Any]) -> str:
    try:
        choices = payload["choices"]
        message = choices[0]["message"]
        content = message["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GrokAPIError("API response did not contain choices[0].message.content") from exc
    if not isinstance(content, str):
        raise GrokAPIError("API response content was not a string")
    return content


def send_prompt(
    prompt: str,
    api_key: str,
    settings: Settings | None = None,
    opener: Any = None,
) -> str:
    """POST one user prompt to /v1/chat/completions and return the assistant text."""
    if not prompt.strip():
        raise GrokAPIError("Prompt is empty")
    cfg = settings or Settings()
    url = cfg.api_base.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "grok-bot/1.0",
        },
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=cfg.timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise GrokAPIError(f"HTTP {exc.code} from {url}: {detail[:400]}") from exc
    except urllib.error.URLError as exc:
        raise GrokAPIError(f"Could not reach {url}: {exc.reason}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise GrokAPIError("API returned non-JSON") from exc
    if not isinstance(payload, dict):
        raise GrokAPIError("API returned a JSON value that is not an object")
    return extract_reply(payload)
