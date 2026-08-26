"""Offline: /chat usage parse and model switch. No live API."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from grok_bot_tui.app import SessionState, handle_command
from grok_bot_tui.client import GrokClient
from grok_bot_tui.config import DEFAULT_MODEL, build_parser
from grok_bot_tui.usage import append_usage_line, format_meter, parse_usage


def test_help_lists_minimal_commands() -> None:
    text = build_parser().format_help()
    for name in ("/chat", "/gui", "/login", "/agents", "/back", "/help", "/quit"):
        assert name in text
    assert "/send" not in text
    assert "https://grok.com" not in text


def test_model_switch() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    assert handle_command("/model", state).message.endswith("grok-4.6")
    assert handle_command("/model grok-4.6", state).kind == "model"
    assert state.model == "grok-4.6"


def test_parse_usage_omits_when_missing() -> None:
    assert parse_usage({}) is None
    assert parse_usage({"usage": {"input_tokens": 9, "output_tokens": 3}}) == {
        "input_tokens": 9,
        "output_tokens": 3,
    }
    assert format_meter(None, 0, 0) == ""
    assert "in:9" in format_meter({"input_tokens": 9, "output_tokens": 3}, 9, 3)


def test_complete_records_usage_when_present() -> None:
    body = {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "ok"}],
            }
        ],
        "usage": {"input_tokens": 11, "output_tokens": 4},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with GrokClient(
        api_key="test-key",
        model=DEFAULT_MODEL,
        timeout=5.0,
        base_url="https://api.x.ai/v1",
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.complete([{"role": "user", "content": "Hi"}]) == "ok"
        assert client.last_usage == {"input_tokens": 11, "output_tokens": 4}


def test_usage_jsonl_append(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    append_usage_line(
        {"input_tokens": 2, "output_tokens": 5},
        session="grok-bot",
        model="grok-4.6",
        path=path,
    )
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["input_tokens"] == 2
    assert row["session"] == "grok-bot"
    assert "api_key" not in row
