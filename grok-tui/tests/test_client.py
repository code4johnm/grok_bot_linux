"""Offline HTTP mocks. No real API key and no network."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from grok_tui.app import ChatState, handle_command, main
from grok_tui.client import (
    GrokAPIError,
    GrokClient,
    delta_from_event,
    error_message_from_body,
    output_text,
    parse_sse_data_line,
    redact_headers,
)
from grok_tui.config import DEFAULT_MODEL, MissingAPIKeyError, load_config

COMPLETED = {
    "id": "resp_test",
    "object": "response",
    "status": "completed",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "Hello from Grok."}],
        }
    ],
}


def _client(handler: httpx.MockTransport | None = None, **kwargs) -> GrokClient:
    transport = handler if handler is not None else httpx.MockTransport(lambda r: httpx.Response(200, json=COMPLETED))
    return GrokClient(
        api_key="test-key",
        model=DEFAULT_MODEL,
        timeout=5.0,
        base_url="https://api.x.ai/v1",
        transport=transport,
    )


def test_client_source_has_no_ui_imports() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("src/grok_tui/client.py").read_text()
    for name in ("prompt_toolkit", "rich", "textual", "curses"):
        assert name not in source


def test_output_text_from_docs_shape() -> None:
    assert output_text(COMPLETED) == "Hello from Grok."


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
    assert text == "Hello from Grok."
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
        'data: {"type":"response.completed","response":'
        + json.dumps(COMPLETED)
        + "}\n\n",
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
        assert "".join(client.stream_text([{"role": "user", "content": "Hi"}])) == "Hello from Grok."


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


def test_module_exits_nonzero_without_key() -> None:
    env = os.environ.copy()
    env.pop("XAI_API_KEY", None)
    env.pop("GROK_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "grok_tui"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "Missing API key" in proc.stderr
    assert "XAI_API_KEY" in proc.stderr


def test_missing_key_exits_nonzero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        load_config([])
    code = main([])
    assert code == 1
    err = capsys.readouterr().err
    assert "XAI_API_KEY" in err
    assert "GROK_API_KEY" in err


def test_xai_key_wins_over_grok_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "from-xai")
    monkeypatch.setenv("GROK_API_KEY", "from-grok")
    cfg = load_config(["--model", "grok-4.6"])
    assert cfg.api_key == "from-xai"
    assert cfg.model == DEFAULT_MODEL


def test_grok_key_fallback_and_system_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("GROK_API_KEY", "from-grok")
    monkeypatch.setenv("GROK_SYSTEM", "Be terse.")
    cfg = load_config([])
    assert cfg.api_key == "from-grok"
    assert cfg.system == "Be terse."


def test_commands_clear_quit_help_model() -> None:
    state = ChatState(system="sys", model="grok-4.6")
    state.messages.append({"role": "user", "content": "hi"})
    assert handle_command("/clear", state).kind == "clear"
    assert state.messages == [{"role": "system", "content": "sys"}]
    assert handle_command("/quit", state).kind == "quit"
    assert handle_command("/exit", state).kind == "quit"
    help_result = handle_command("/help", state)
    assert help_result is not None and "/clear" in help_result.message
    assert handle_command("/model", state).message.endswith("grok-4.6")
    assert handle_command("/model grok-4.6", state).kind == "model"
    assert handle_command("hello", state) is None
