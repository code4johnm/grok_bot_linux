"""Offline: Grok Bot transcript parsing. Newest-first API order."""

from __future__ import annotations

import base64
import json

from grok_bot_tui.grok_bot_client import (
    _assistant_text,
    _newest_assistant,
    transcript_messages,
)


def _entry(seq: int, payload: dict) -> dict:
    body = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return {"seq": str(seq), "entryKind": payload.get("kind") or "message", "body": body}


def test_assistant_text_uses_newest_seq_not_list_order() -> None:
    agent = "bot-new"
    entries = [
        _entry(
            50,
            {
                "kind": "message",
                "role": "assistant",
                "content": "newest",
                "toAgent": {"id": agent, "name": "New"},
            },
        ),
        _entry(
            10,
            {
                "kind": "message",
                "role": "assistant",
                "content": "oldest",
                "toAgent": {"id": agent, "name": "New"},
            },
        ),
    ]
    assert _assistant_text(entries, agent) == "newest"
    assert _newest_assistant(entries, agent)[0] == 50


def test_assistant_text_ignores_other_bots() -> None:
    entries = [
        _entry(
            9,
            {
                "kind": "message",
                "role": "assistant",
                "content": "other",
                "toAgent": {"id": "other-bot", "name": "Other"},
            },
        ),
        _entry(
            8,
            {
                "kind": "message",
                "role": "assistant",
                "content": "mine",
                "toAgent": {"id": "my-bot", "name": "Mine"},
            },
        ),
    ]
    assert _assistant_text(entries, "my-bot") == "mine"


def test_transcript_messages_chronological_and_dedupes_send() -> None:
    agent = "bot-a"
    entries = [
        _entry(4, {"kind": "message", "role": "assistant", "content": "pong", "toAgent": {"id": agent}}),
        _entry(3, {"kind": "message", "role": "user", "content": "ping"}),
        _entry(2, {"kind": "send-message", "id": "t0s0", "message": {"type": "text", "content": "ping"}}),
        _entry(1, {"kind": "message", "role": "user", "content": "hello"}),
    ]
    rows = transcript_messages(entries, agent)
    assert [r["role"] for r in rows] == ["user", "user", "assistant"]
    assert [r["content"] for r in rows] == ["hello", "ping", "pong"]
