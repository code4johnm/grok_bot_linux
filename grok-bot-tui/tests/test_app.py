"""Offline: layout, /gui, /chat commands. No live key. No grok.com."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from grok_bot_tui import DEFAULT_BOT, PROG, TITLE
from grok_bot_tui.app import (
    BACK_BUTTON,
    BACK_KEYS_HINT,
    HELP,
    SessionState,
    handle_command,
    render_chat,
    render_footer,
    render_header,
    render_screen,
    render_transcript,
)
from grok_bot_tui.config import DEFAULT_MODEL, build_parser, load_config
from grok_bot_tui.gui import DESKTOP_X86_ONLY, MISSING_DESKTOP, launch_grok_bot

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parent


def _state(*, has_api: bool = False, bot: str = DEFAULT_BOT) -> SessionState:
    return SessionState(system="sys", model="grok-4.6", has_api=has_api, bot_name=bot)


def test_help_and_module_branding() -> None:
    text = build_parser().format_help()
    assert TITLE == "Grok GUI TUI shell"
    assert TITLE in text or PROG in text
    assert "not Grok" in text
    assert "Grok GUI companion" not in text
    assert "this is Grok" not in text.lower()
    assert "https://grok.com" not in text
    assert "/gui" in text
    assert "/login" in text


def test_module_help_exits_zero_without_key() -> None:
    env = os.environ.copy()
    env.pop("XAI_API_KEY", None)
    env.pop("GROK_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "grok_bot_tui", "--help"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert PROG in proc.stdout
    assert "https://grok.com" not in proc.stdout
    assert "Grok GUI companion" not in proc.stdout


def test_load_config_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    cfg = load_config([])
    assert cfg.has_api_key is False
    assert cfg.model == DEFAULT_MODEL


def test_layout_is_one_thread() -> None:
    state = _state(has_api=True)
    state.view = "chat"
    screen = render_screen(state)
    assert render_header(state) == "Grok GUI TUI shell"
    assert "signed in" in render_footer(state)
    assert "shell" in render_footer(state)
    assert render_transcript(state) == "(no messages)"
    assert "Grok GUI TUI shell" in screen
    assert BACK_BUTTON in screen
    assert BACK_KEYS_HINT in screen
    state.messages.append({"role": "user", "content": "hi"})
    state.messages.append({"role": "assistant", "content": "hello"})
    body = render_transcript(state)
    assert "you: hi" in body
    assert "bot: hello" in body
    chat = render_chat(state)
    assert chat.splitlines()[0].endswith(BACK_KEYS_HINT)
    assert BACK_BUTTON in chat
    assert "you: hi" in chat


def test_gui_launches_desktop_on_x86_never_grok_com(tmp_path: Path) -> None:
    desktop = tmp_path / "grok-bot"
    desktop.write_text("#!/bin/sh\n")
    desktop.chmod(0o755)
    spawned: list[list[str]] = []

    def fake_popen(cmd: list[str], **_kwargs: object) -> object:
        spawned.append(cmd)
        return object()

    msg = launch_grok_bot(popen=fake_popen, candidates=[desktop], arch="x86_64")
    assert spawned == [[str(desktop)]]
    assert "grok.com" not in msg
    assert "Launched grok-bot" in msg


def test_gui_aarch64_does_not_launch(tmp_path: Path) -> None:
    desktop = tmp_path / "grok-bot"
    desktop.write_text("#!/bin/sh\n")
    desktop.chmod(0o755)
    spawned: list[list[str]] = []

    def fake_popen(cmd: list[str], **_kwargs: object) -> object:
        spawned.append(cmd)
        return object()

    msg = launch_grok_bot(popen=fake_popen, candidates=[desktop], arch="aarch64")
    assert spawned == []
    assert msg == DESKTOP_X86_ONLY
    assert "grok.com" not in msg
    assert "Chat still works" in msg


def test_find_electron_skips_launch_sh(tmp_path: Path) -> None:
    from grok_bot_tui.gui import find_electron

    sh = tmp_path / "launch.sh"
    sh.write_text("#!/bin/sh\n")
    sh.chmod(0o755)
    electron = tmp_path / "grok-bot"
    electron.write_text("#!/bin/sh\n")
    electron.chmod(0o755)
    (tmp_path / "chrome-sandbox").write_text("")
    assert find_electron(candidates=[sh, electron]) == electron
    assert find_electron(candidates=[sh]) is None


def test_gui_missing_on_x86_no_browser() -> None:
    msg = launch_grok_bot(popen=lambda *_a, **_k: None, candidates=[], arch="x86_64")
    assert msg == MISSING_DESKTOP
    assert "grok.com" not in msg
    assert "Chat still works" in msg


def test_commands_gui_clear_quit_help_bot_chat() -> None:
    state = _state(has_api=True)
    state.view = "chat"
    assert handle_command("/gui", state).kind == "gui"
    assert handle_command("/quit", state).kind == "quit"
    help_result = handle_command("/help", state)
    assert TITLE in help_result.message
    assert "/gui" in help_result.message
    assert "/login" in help_result.message
    assert "/agents" in help_result.message
    assert "/back" in help_result.message
    assert "Esc / ←" in help_result.message
    assert "This is not Grok" in help_result.message
    assert "Grok GUI companion" not in help_result.message
    assert handle_command("/clear", state).kind == "clear"
    typed = handle_command("hello there", state)
    assert typed.kind == "chat"
    assert typed.send_text == "hello there"
    slash = handle_command("/chat later", state)
    assert slash.send_text == "later"
    assert "Chat stays in this terminal" in help_result.message
    assert "Messages to Bots run in Grok Bot" not in help_result.message
    assert "Gmail" not in help_result.message


def test_send_chat_stays_in_terminal() -> None:
    import base64
    import json

    import httpx

    from grok_bot_tui.agents import Agent
    from grok_bot_tui.app import NEED_BOT_MSG, _send_chat
    from grok_bot_tui.grok_bot_client import GrokBotClient

    state = _state(has_api=True)
    state.view = "chat"
    state.agents = [Agent(id="bot-ops", name="Ops", blurb="queue")]
    notes: list[str] = []
    _send_chat(state, None, "hello", emit=notes.append)
    assert NEED_BOT_MSG in notes
    assert "Gmail" not in NEED_BOT_MSG
    assert any(item.get("role") == "user" and item.get("content") == "hello" for item in state.messages)
    assert any(item.get("role") == "assistant" and NEED_BOT_MSG in (item.get("content") or "") for item in state.messages)
    source = (PKG / "src/grok_bot_tui/app.py").read_text(encoding="utf-8")
    send = source.split("def _send_chat", 1)[1].split("\ndef main", 1)[0]
    assert "launch_grok_bot" not in send
    assert "XAI_API_KEY" not in send
    assert "webbrowser" not in send

    lists = {"n": 0}
    reply_body = base64.b64encode(
        json.dumps(
            {
                "kind": "message",
                "role": "assistant",
                "content": "Hi there",
                "isStreaming": False,
            }
        ).encode("utf-8")
    ).decode("ascii")

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        if path.endswith("ListGrokBotTranscriptEntries"):
            lists["n"] += 1
            if lists["n"] == 1:
                return httpx.Response(200, json={"generation": 1, "entries": []})
            return httpx.Response(
                200,
                json={
                    "generation": 1,
                    "entries": [{"seq": "2", "entryKind": "message", "body": reply_body}],
                },
            )
        if path.endswith("CommitGrokBotTranscriptEntries"):
            assert b"bot-ops" in request.content
            assert b"send-message" in request.content
            return httpx.Response(200, json={"committedCount": 1})
        return httpx.Response(404, json={"message": path})

    client = GrokBotClient(
        "test-grok-bot-token",
        timeout=5.0,
        transport=httpx.MockTransport(handler),
    )
    client.poll_sleep = lambda _s: None
    client.poll_interval = 0
    notes = []
    _send_chat(state, client, "hello", emit=notes.append)
    client.close()
    assert any(item.get("role") == "user" and item.get("content") == "hello" for item in state.messages)
    assert any(item.get("role") == "assistant" and "Hi there" in (item.get("content") or "") for item in state.messages)
    assert state.streaming is False


def test_back_from_chat_to_agents() -> None:
    state = _state(has_api=True)
    state.auth_state = "signed_in"
    state.view = "chat"
    state.messages.append({"role": "user", "content": "hi"})
    result = handle_command("/back", state)
    assert result.kind == "back"
    assert state.view == "agents"
    assert any(item.get("content") == "hi" for item in state.messages)
    assert handle_command("/bots", state).kind == "back"
    signed_out = _state(has_api=False)
    assert handle_command("/back", signed_out).kind == "login"


def test_chat_without_key() -> None:
    state = _state(has_api=False)
    result = handle_command("hello", state)
    assert result.kind == "login"
    assert handle_command("/chat", state).kind == "login"
    assert handle_command("/login", state).kind == "login"


def test_package_is_not_grok() -> None:
    readme = (PKG / "README.md").read_text()
    blob = "\n".join(
        [
            HELP,
            build_parser().format_help(),
            readme,
            (PKG / "src/grok_bot_tui/__init__.py").read_text(),
        ]
    )
    assert PROG in blob
    assert "Grok GUI companion" not in blob
    assert "this is Grok" not in blob.lower()
    assert "https://grok.com" not in blob
    assert "grok-tui-shell" in readme
    assert "cursor.com/bot/onboarding" in readme
    assert "sand-client-persistence" in readme
    assert "from signed-in Grok Bot" in readme
    assert "does **not** read Cookies" in readme
    assert "does **not** call the official `grok` CLI" in readme
    assert "Sales Outbound" in readme  # documented as stale-install symptom only
    assert "0.7.2" in readme
    assert "Chat stays in this terminal" in readme or "chat stays" in readme.lower()
    assert "Raspberry Pi" in readme
    assert "install.sh" in readme
    assert "systemctl --user" in readme
    assert "config.json" in readme


def test_electron_packaging_untouched() -> None:
    for relative in ("launch.sh", "install.sh", "uninstall.sh", "app/README.md", "scripts/install-cli.sh"):
        assert (REPO / relative).is_file(), relative
    assert "Electron" in (REPO / "app/README.md").read_text()
    assert "chrome-sandbox" in (REPO / "launch.sh").read_text()


def test_no_official_grok_cli_module() -> None:
    assert not (PKG / "src/grok_bot_tui/grok.py").exists()
    source = (PKG / "src/grok_bot_tui/app.py").read_text()
    assert "Grok Build TUI" not in source
    assert "find_grok_cli" not in source
    assert "grok login" not in source
    assert "accounts.x.ai" not in source
    assert "start_device_login" not in source
