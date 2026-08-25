"""Offline: layout, /gui, /chat commands. No live key. No grok.com."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from grok_bot_tui import DEFAULT_BOT, PROG, TITLE
from grok_bot_tui.app import (
    HELP,
    SessionState,
    handle_command,
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
    assert PROG in text
    assert TITLE == "grok-bot-tui"
    assert "This is not Grok" in text or "this is not Grok" in text.lower()
    assert "Grok GUI companion" not in text
    assert "this is Grok" not in text.lower()
    assert "https://grok.com" not in text
    assert "/gui" in text
    assert "/chat" in text


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
    state = _state()
    screen = render_screen(state)
    assert render_header(state) == "grok-bot  ·  grok-bot-tui"
    assert render_footer() == "grok-bot-tui"
    assert render_transcript(state) == "(no messages)"
    assert screen.startswith("grok-bot  ·  grok-bot-tui")
    assert screen.endswith("grok-bot-tui")
    state.messages.append({"role": "user", "content": "hi"})
    state.messages.append({"role": "assistant", "content": "hello"})
    body = render_transcript(state)
    assert "you: hi" in body
    assert "bot: hello" in body


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


def test_gui_missing_on_x86_no_browser() -> None:
    msg = launch_grok_bot(popen=lambda *_a, **_k: None, candidates=[], arch="x86_64")
    assert msg == MISSING_DESKTOP
    assert "grok.com" not in msg
    assert "Chat still works" in msg


def test_commands_gui_clear_quit_help_bot_chat() -> None:
    state = _state(has_api=True)
    assert handle_command("/gui", state).kind == "gui"
    assert handle_command("/quit", state).kind == "quit"
    help_result = handle_command("/help", state)
    assert PROG in help_result.message
    assert "/gui" in help_result.message
    assert "/chat" in help_result.message
    assert "/bot" in help_result.message
    assert "This is not Grok" in help_result.message
    assert "Grok GUI companion" not in help_result.message
    assert "/grok " not in help_result.message
    assert handle_command("/clear", state).kind == "clear"
    assert handle_command("/bot ops", state).message == "Thread: ops"
    assert state.bot_name == "ops"
    typed = handle_command("hello there", state)
    assert typed.kind == "chat"
    assert typed.send_text == "hello there"
    slash = handle_command("/chat later", state)
    assert slash.send_text == "later"


def test_chat_without_key() -> None:
    state = _state(has_api=False)
    result = handle_command("hello", state)
    assert result.kind == "need_key"
    assert "XAI_API_KEY" in result.message
    assert handle_command("/chat", state).kind == "need_key"


def test_package_is_not_grok() -> None:
    blob = "\n".join(
        [
            HELP,
            build_parser().format_help(),
            (PKG / "README.md").read_text(),
            (PKG / "src/grok_bot_tui/__init__.py").read_text(),
        ]
    )
    assert PROG in blob
    assert "Grok GUI companion" not in blob
    assert "this is Grok" not in blob.lower()
    assert "https://grok.com" not in blob


def test_electron_packaging_untouched() -> None:
    for relative in ("launch.sh", "install.sh", "uninstall.sh", "app/README.md", "scripts/install-cli.sh"):
        assert (REPO / relative).is_file(), relative
    assert "Electron" in (REPO / "app/README.md").read_text()
    assert "chrome-sandbox" in (REPO / "launch.sh").read_text()


def test_no_official_grok_cli_module() -> None:
    assert not (PKG / "src/grok_bot_tui/grok.py").exists()
    source = (PKG / "src/grok_bot_tui/app.py").read_text()
    assert "find_grok" not in source
    assert "Grok Build TUI" not in source
