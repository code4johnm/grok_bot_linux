"""Offline: prompt cache, sessions, usage parse, /analyze without a key."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from grok_bot_tui.app import SessionState, analyze_request, handle_command
from grok_bot_tui.client import GrokClient
from grok_bot_tui.config import DEFAULT_MODEL, build_parser
from grok_bot_tui.prompts import CATALOG, NOTICE, PromptCatalog, PromptError
from grok_bot_tui.sessions import SessionStore
from grok_bot_tui.usage import append_usage_line, format_meter, parse_usage


def test_help_lists_new_commands() -> None:
    text = build_parser().format_help()
    for name in ("/prompt", "/analyze", "/sessions", "/model", "/gui"):
        assert name in text


def test_prompt_list_is_offline() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    result = handle_command("/prompt", state)
    assert result.kind == "prompt"
    assert "xai-org/grok-prompts" in result.message
    for pid in ("grok4", "grok3", "ask", "analyze", "safety-4", "safety-mini", "code-rc1"):
        assert pid in result.message
        assert pid in CATALOG


def test_prompt_fetch_is_mocked_and_cached(tmp_path: Path) -> None:
    seen: list[str] = []

    def fake_get(url: str) -> str:
        seen.append(url)
        return "OFFICIAL PROMPT TEXT"

    catalog = PromptCatalog(cache_dir=tmp_path / "prompts", fetcher=fake_get)
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    result = handle_command("/prompt grok4", state, prompts=catalog)
    assert result.kind == "prompt"
    assert state.prompt_id == "grok4"
    assert state.system == "OFFICIAL PROMPT TEXT"
    assert state.messages[0]["content"] == "OFFICIAL PROMPT TEXT"
    assert (tmp_path / "prompts" / "NOTICE").read_text(encoding="utf-8") == NOTICE
    assert "AGPL" in (tmp_path / "prompts" / "NOTICE").read_text(encoding="utf-8")
    assert "github.com/xai-org/grok-prompts" in (tmp_path / "prompts" / "NOTICE").read_text(encoding="utf-8")
    first = list(seen)
    handle_command("/prompt grok4", state, prompts=catalog)
    assert seen == first  # cache hit, no second fetch

    off = handle_command("/prompt off", state, prompts=catalog)
    assert off.kind == "prompt"
    assert state.prompt_id is None
    assert state.system == "sys"


def test_prompt_unknown_id() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    catalog = PromptCatalog(cache_dir=Path("/unused"), fetcher=lambda url: "")
    result = handle_command("/prompt nope", state, prompts=catalog)
    assert "Unknown prompt" in result.message
    with pytest.raises(PromptError):
        catalog.get("nope")


def test_analyze_without_key_notes_url() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    result = handle_command("/analyze https://x.com/lummox_eth/status/2091964274432413987", state)
    assert result.kind == "need_key"
    assert "XAI_API_KEY" in result.message
    assert state.notes == ["analyze: https://x.com/lummox_eth/status/2091964274432413987"]
    assert result.send_text is None


def test_analyze_with_key_sends_explain_request() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    url = "https://example.com/post"
    result = handle_command(f"/analyze {url}", state)
    assert result.kind == "analyze"
    assert result.send_text == analyze_request(url)
    assert url in result.send_text
    assert "scraped" in result.send_text
    assert handle_command("/analyze not-a-url", state).kind == "analyze"


def test_sessions_new_open_forget(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions")
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    state.notes.append("keep-me")
    handle_command("/new demo", state, sessions=store)
    assert state.name == "demo"
    assert state.notes == []
    assert "demo" in store.list_names()
    state.notes.append("later")
    store.save(state.snapshot())
    handle_command("/new other", state, sessions=store)
    opened = handle_command("/open demo", state, sessions=store)
    assert opened.kind == "open"
    assert state.name == "demo"
    assert "later" in state.notes
    listed = handle_command("/sessions", state, sessions=store)
    assert "demo" in listed.message
    forgot = handle_command("/forget demo", state, sessions=store)
    assert forgot.kind == "forget"
    assert "demo" not in store.list_names()
    assert handle_command("/clear", state).kind == "clear"
    assert store.path_for("other").is_file()


def test_session_file_has_no_secrets(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions")
    store.save(
        {
            "name": "safe",
            "model": "grok-4.6",
            "notes": ["hi"],
            "messages": [{"role": "user", "content": "hi"}],
            "api_key": "should-not-be-saved",
            "Authorization": "Bearer secret",
        }
    )
    raw = store.path_for("safe").read_text(encoding="utf-8")
    assert "should-not-be-saved" not in raw
    assert "Bearer" not in raw
    loaded = store.load("safe")
    assert loaded is not None
    assert "api_key" not in loaded


def test_parse_usage_omits_when_missing() -> None:
    assert parse_usage({}) is None
    assert parse_usage({"output": []}) is None
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
        session="default",
        model="grok-4.6",
        path=path,
    )
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert row["input_tokens"] == 2
    assert row["output_tokens"] == 5
    assert row["session"] == "default"
    assert "api_key" not in row


def test_model_switch() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    assert handle_command("/model", state).message.endswith("grok-4.6")
    assert handle_command("/model grok-4.6", state).kind == "model"
    assert state.model == "grok-4.6"
