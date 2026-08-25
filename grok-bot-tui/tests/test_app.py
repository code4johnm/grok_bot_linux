"""Companion shell: branding, /gui (mocked), notes, optional API. No live key."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from grok_bot_tui import PROG, STATUS, TITLE
from grok_bot_tui.app import HELP, PANE_API, SessionState, handle_command
from grok_bot_tui.config import DEFAULT_MODEL, build_parser, load_config
from grok_bot_tui.gui import OFFICIAL_GUI_URL, open_official_gui

PKG = Path(__file__).resolve().parents[1]


def test_help_shows_companion_branding() -> None:
    text = build_parser().format_help()
    assert PROG in text
    assert TITLE in text
    assert "companion" in text.lower()
    assert "Grok terminal" not in text
    assert OFFICIAL_GUI_URL in text


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
    assert TITLE in proc.stdout
    assert PROG in proc.stdout
    assert "companion" in proc.stdout.lower()


def test_load_config_without_key_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    cfg = load_config([])
    assert cfg.api_key is None
    assert cfg.has_api_key is False
    assert cfg.gui_url == OFFICIAL_GUI_URL


def test_xai_key_wins_over_grok_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "from-xai")
    monkeypatch.setenv("GROK_API_KEY", "from-grok")
    cfg = load_config(["--model", "grok-4.6"])
    assert cfg.api_key == "from-xai"
    assert cfg.model == DEFAULT_MODEL


def test_gui_open_is_mocked() -> None:
    seen: list[str] = []

    def fake_open(url: str) -> bool:
        seen.append(url)
        return True

    msg = open_official_gui(OFFICIAL_GUI_URL, opener=fake_open)
    assert seen == [OFFICIAL_GUI_URL]
    assert msg == f"Opened official Grok GUI: {OFFICIAL_GUI_URL}"


def test_gui_open_failure_is_one_line() -> None:
    def fake_open(url: str) -> bool:
        raise OSError("no display")

    msg = open_official_gui(OFFICIAL_GUI_URL, opener=fake_open)
    assert "Could not open official Grok GUI" in msg
    assert OFFICIAL_GUI_URL in msg


def test_commands_gui_clear_quit_help_notes() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    assert state.mode == "notes"
    assert handle_command("/gui", state).kind == "gui"
    state.notes.append("keep")
    state.messages.append({"role": "user", "content": "hi"})
    assert handle_command("/clear", state).kind == "clear"
    assert state.notes == []
    assert state.messages == [{"role": "system", "content": "sys"}]
    assert handle_command("/quit", state).kind == "quit"
    help_result = handle_command("/help", state)
    assert help_result is not None
    assert "/gui" in help_result.message
    assert "/prompt" in help_result.message
    assert "/analyze" in help_result.message
    assert "/sessions" in help_result.message
    assert "/model" in help_result.message
    assert "/plan" in help_result.message
    assert "/send" in help_result.message
    assert TITLE in help_result.message
    assert PANE_API in help_result.message
    assert handle_command("/notes", state).kind == "notes"
    assert handle_command("remember this", state) is None


def test_chat_without_key_stays_on_notes() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    result = handle_command("/chat", state)
    assert result.kind == "need_key"
    assert "XAI_API_KEY" in result.message
    assert PANE_API in result.message
    assert state.mode == "notes"


def test_chat_with_key_switches_and_can_send() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    assert state.mode == "api"
    result = handle_command("/chat hello", state)
    assert result.kind == "chat"
    assert result.send_text == "hello"
    assert PANE_API in result.message
    assert handle_command("/notes", state).kind == "notes"
    assert state.mode == "notes"


def test_package_does_not_claim_to_be_grok_the_product() -> None:
    """Binary/help/README identify as grok-bot-tui companion, not Grok itself."""
    help_text = HELP + "\n" + build_parser().format_help()
    readme = (PKG / "README.md").read_text()
    init = (PKG / "src/grok_bot_tui/__init__.py").read_text()
    blob = "\n".join([help_text, readme, init])
    assert PROG in blob
    assert TITLE in blob
    assert STATUS in blob
    assert "Grok terminal" not in blob
    assert "this TUI is Grok" not in blob.lower()
    assert "is Grok bot" not in blob
    # Hyphenated CLI name is required; spaced "Grok bot" as *this* product is not.
    for path in (PKG / "src/grok_bot_tui").glob("*.py"):
        text = path.read_text()
        assert "Grok terminal" not in text
