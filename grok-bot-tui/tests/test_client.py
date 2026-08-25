"""Offline HTTP mocks. No real API key and no network."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from grok_bot_tui.client import (
    GrokAPIError,
    GrokClient,
    delta_from_event,
    error_message_from_body,
    output_text,
    parse_sse_data_line,
    redact_headers,
)
from grok_bot_tui.config import DEFAULT_MODEL

COMPLETED = {
    "id": "resp_test",
    "object": "response",
    "status": "completed",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Hello from companion."}],
        }
    ],
}


def _client(handler: httpx.MockTransport | None = None) -> GrokClient:
    transport = handler if handler is not None else httpx.MockTransport(lambda r: httpx.Response(200, json=COMPLETED))
    return GrokClient(
        api_key="test-key",
        model=DEFAULT_MODEL,
        timeout=5.0,
        base_url="https://api.x.ai/v1",
        transport=transport,
    )


def test_client_source_has_no_ui_imports() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("src/grok_bot_tui/client.py").read_text()
    for name in ("prompt_toolkit", "rich", "textual", "curses", "webbrowser"):
        assert name not in source


def test_output_text_from_docs_shape() -> None:
    assert output_text(COMPLETED) == "Hello from companion."


def test_redact_authorization() -> None:
    redacted = redact_headers({"Authorization": "Bearer super-secret", "Content-Type": "application/json"})
    assert redacted["Authorization"] == "Bearer [redacted]"
    assert "super-secret" not in json.dumps(redacted)


def test_complete_posts_responses_and_keeps_history_shape() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=COMPLETED)

    with _client(httpx.MockTransport(handler)) as client:
        text = client.complete(
            [
                {"role": "system", "content": "Be brief."},
                {"role": "user", "content": "Hi"},
            ]
        )
    assert text == "Hello from companion."
    assert len(seen) == 1
    assert seen[0].url.path == "/v1/responses"
    body = json.loads(seen[0].content)
    assert body["model"] == DEFAULT_MODEL
    assert body["store"] is False
    assert "stream" not in body
    assert body["input"][1]["content"] == "Hi"
    assert seen[0].headers["Authorization"] == "Bearer test-key"


def test_stream_text_yields_output_text_deltas() -> None:
    chunks = [
        'data: {"type":"response.output_text.delta","delta":"Hel"}\n\n',
        'data: {"type":"response.output_text.delta","delta":"lo"}\n\n',
        'data: {"type":"response.completed","response":' + json.dumps(COMPLETED) + "}\n\n",
        "data: [DONE]\n\n",
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        assert request.url.path == "/v1/responses"
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="".join(chunks),
        )

    with _client(httpx.MockTransport(handler)) as client:
        assert "".join(client.stream_text([{"role": "user", "content": "Hi"}])) == "Hello"


def test_stream_falls_back_to_completed_output_when_no_deltas() -> None:
    payload = 'data: {"type":"response.completed","response":' + json.dumps(COMPLETED) + "}\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=payload,
        )

    with _client(httpx.MockTransport(handler)) as client:
        assert "".join(client.stream_text([{"role": "user", "content": "Hi"}])) == "Hello from companion."


def test_rate_limit_is_one_line_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"message": "Rate limit exceeded", "code": "rate_limit"}},
        )

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(GrokAPIError, match="Rate limit exceeded") as excinfo:
            client.complete([{"role": "user", "content": "Hi"}])
    assert "test-key" not in str(excinfo.value)
    assert "Authorization" not in str(excinfo.value)


def test_stream_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Too many requests"}})

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(GrokAPIError, match="Too many requests"):
            list(client.stream_text([{"role": "user", "content": "Hi"}]))


def test_network_error_does_not_include_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(GrokAPIError, match="Network error") as excinfo:
            client.complete([{"role": "user", "content": "Hi"}])
    assert "test-key" not in str(excinfo.value)


def test_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(GrokAPIError, match="timed out"):
            client.complete([{"role": "user", "content": "Hi"}])


def test_parse_sse_and_delta_helpers() -> None:
    assert parse_sse_data_line("data: [DONE]") is None
    assert parse_sse_data_line(": keep-alive") is None
    event = parse_sse_data_line('data: {"type":"response.output_text.delta","delta":"x"}')
    assert event is not None
    assert delta_from_event(event) == "x"
    assert error_message_from_body(None, 503) == "Server error (HTTP 503)."
    assert error_message_from_body(None, 429) == "Rate limited (HTTP 429)."
