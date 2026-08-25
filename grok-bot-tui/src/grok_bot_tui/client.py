"""xAI Responses API client. HTTP only — no UI imports."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

import httpx

from grok_bot_tui.usage import parse_usage

DEFAULT_BASE_URL = "https://api.x.ai/v1"


class GrokAPIError(Exception):
    """One-line, safe-to-print API or network error (no secrets)."""


def redact_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Copy headers with Authorization redacted. Never log the raw key."""
    redacted: dict[str, str] = {}
    for key, value in (headers or {}).items():
        if key.lower() == "authorization":
            redacted[key] = "Bearer [redacted]"
        else:
            redacted[key] = value
    return redacted


def output_text(payload: Mapping[str, Any] | None) -> str:
    """Extract assistant text from a Responses API body (docs.x.ai generate-text)."""
    if not payload:
        return ""
    convenience = payload.get("output_text")
    if isinstance(convenience, str) and convenience:
        return convenience

    chunks: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, Mapping):
            continue
        if item.get("type") not in (None, "message"):
            continue
        content = item.get("content")
        if isinstance(content, str):
            chunks.append(content)
            continue
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, Mapping):
                continue
            if part.get("type") in ("output_text", "text"):
                text = part.get("text")
                if isinstance(text, str) and text:
                    chunks.append(text)
    return "".join(chunks)


def delta_from_event(event: Mapping[str, Any]) -> str:
    """Token delta from a Responses streaming SSE event."""
    event_type = event.get("type")
    if event_type == "response.output_text.delta":
        delta = event.get("delta")
        return delta if isinstance(delta, str) else ""
    if event_type == "response.content_part.delta":
        delta = event.get("delta")
        if isinstance(delta, Mapping):
            text = delta.get("text")
            return text if isinstance(text, str) else ""
    if isinstance(event_type, str) and event_type.endswith(".delta"):
        delta = event.get("delta")
        if isinstance(delta, str):
            return delta
    return ""


def parse_sse_data_line(line: str) -> dict[str, Any] | None:
    """Parse one SSE `data:` line. Returns None for keep-alives and [DONE]."""
    raw = line.strip()
    if not raw or raw.startswith(":"):
        return None
    if raw.startswith("event:"):
        return None
    if raw.startswith("data:"):
        raw = raw[5:].strip()
    if not raw or raw == "[DONE]":
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def error_message_from_body(body: Any, status_code: int) -> str:
    if isinstance(body, Mapping):
        err = body.get("error")
        if isinstance(err, Mapping):
            msg = err.get("message") or err.get("code")
            if msg:
                return str(msg)
        if isinstance(err, str) and err:
            return err
        msg = body.get("message")
        if isinstance(msg, str) and msg:
            return msg
    if status_code == 429:
        return "Rate limited (HTTP 429)."
    if status_code >= 500:
        return f"Server error (HTTP {status_code})."
    return f"API error (HTTP {status_code})."


class GrokClient:
    """POST /v1/responses against https://api.x.ai/v1 (Responses API)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self.last_usage: dict[str, int] | None = None
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GrokClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _payload(self, messages: list[dict[str, str]], stream: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "input": messages,
            "store": False,
        }
        if stream:
            body["stream"] = True
        return body

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.last_usage = None
        try:
            response = self._http.post("/responses", json=self._payload(messages, stream=False))
        except httpx.TimeoutException as exc:
            raise GrokAPIError("Request timed out.") from exc
        except httpx.RequestError as exc:
            raise GrokAPIError("Network error. Check connectivity and try again.") from exc
        return self._text_from_response(response)

    def stream_text(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """Yield token deltas from Responses API SSE (`stream: true`)."""
        self.last_usage = None
        try:
            with self._http.stream(
                "POST",
                "/responses",
                json=self._payload(messages, stream=True),
            ) as response:
                if response.status_code >= 400:
                    body = self._read_error_body(response)
                    raise GrokAPIError(error_message_from_body(body, response.status_code))
                yield from self._iter_stream(response)
        except GrokAPIError:
            raise
        except httpx.TimeoutException as exc:
            raise GrokAPIError("Request timed out.") from exc
        except httpx.RequestError as exc:
            raise GrokAPIError("Network error. Check connectivity and try again.") from exc

    def _text_from_response(self, response: httpx.Response) -> str:
        body: Any
        try:
            body = response.json()
        except json.JSONDecodeError:
            body = None
        if response.status_code >= 400:
            raise GrokAPIError(error_message_from_body(body, response.status_code))
        text = output_text(body if isinstance(body, Mapping) else None)
        self.last_usage = parse_usage(body if isinstance(body, Mapping) else None)
        return text

    def _read_error_body(self, response: httpx.Response) -> Any:
        raw = response.read()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def _iter_stream(self, response: httpx.Response) -> Iterator[str]:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type and "text/event-stream" not in content_type:
            body = self._read_error_body(response) or {}
            self.last_usage = parse_usage(body if isinstance(body, Mapping) else None)
            text = output_text(body if isinstance(body, Mapping) else None)
            if text:
                yield text
            return

        got_delta = False
        completed_text = ""
        for line in response.iter_lines():
            event = parse_sse_data_line(line)
            if event is None:
                continue
            if event.get("type") == "error" or (event.get("error") and event.get("type") != "response.completed"):
                raise GrokAPIError(error_message_from_body(event, 0) or "API error.")
            delta = delta_from_event(event)
            if delta:
                got_delta = True
                yield delta
                continue
            if event.get("type") == "response.completed":
                inner = event.get("response")
                payload = inner if isinstance(inner, Mapping) else event
                completed_text = output_text(payload)
                self.last_usage = parse_usage(payload)
            elif "output" in event:
                completed_text = output_text(event)
                self.last_usage = parse_usage(event) or self.last_usage
        if not got_delta and completed_text:
            yield completed_text
