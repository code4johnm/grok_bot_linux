"""Companion shell: Grok Bot branding, /gui, official grok. No live key."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from grok_bot_tui import PROG, STATUS, TITLE
from grok_bot_tui.app import HELP, PANE_API, SessionState, handle_command
from grok_bot_tui.config import DEFAULT_MODEL, build_parser, load_config
from grok_bot_tui.gui import GROK_BOT_URL, find_desktop, launch_grok_bot

PKG = Path(__file__).resolve().parents[1]


def test_help_shows_companion_branding() -> None:
    text = build_parser().format_help()
    assert PROG in text
    assert TITLE in text
    assert STATUS == "Grok Bot companion"
    assert "Grok Bot companion" in text
    assert "Grok GUI companion" not in text
    assert "Grok terminal" not in text
    assert GROK_BOT_URL in text
    assert "https://grok.com" not in text
    assert "/grok" in text
    assert "not a replacement" in text.lower() or "launcher" in text.lower()


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
    assert "Grok Bot companion" in proc.stdout
    assert PROG in proc.stdout
    assert "/grok" in proc.stdout
    assert "https://grok.com" not in proc.stdout
    assert "x.ai/bot" in proc.stdout


def test_load_config_without_key_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    cfg = load_config([])
    assert cfg.api_key is None
    assert cfg.has_api_key is False
    assert not hasattr(cfg, "gui_url")


def test_xai_key_wins_over_grok_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY", "from-xai")
    monkeypatch.setenv("GROK_API_KEY", "from-grok")
    cfg = load_config(["--model", "grok-4.6"])
    assert cfg.api_key == "from-xai"
    assert cfg.model == DEFAULT_MODEL


def test_gui_prefers_desktop_over_url(tmp_path: Path) -> None:
    desktop = tmp_path / "grok-bot"
    desktop.write_text("#!/bin/sh\n")
    desktop.chmod(0o755)
    seen_urls: list[str] = []
    spawned: list[list[str]] = []

    def fake_open(url: str) -> bool:
        seen_urls.append(url)
        return True

    def fake_popen(cmd: list[str], **_kwargs: object) -> object:
        spawned.append(cmd)
        return object()

    msg = launch_grok_bot(opener=fake_open, popen=fake_popen, candidates=[desktop])
    assert spawned == [[str(desktop)]]
    assert seen_urls == []
    assert "grok.com" not in msg
    assert str(desktop) in msg


def test_gui_prefers_launch_sh_over_electron_binary(tmp_path: Path) -> None:
    electron_dir = tmp_path / "opt" / "grok-bot"
    electron_dir.mkdir(parents=True)
    binary = electron_dir / "grok-bot"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)
    (electron_dir / "chrome-sandbox").write_text("sandbox")
    (electron_dir / "chrome_100_percent.pak").write_text("pak")
    launcher = tmp_path / "launch.sh"
    launcher.write_text("#!/bin/sh\n")
    launcher.chmod(0o755)

    assert find_desktop([binary, launcher]) == launcher
    spawned: list[list[str]] = []
    seen_urls: list[str] = []

    def fake_open(url: str) -> bool:
        seen_urls.append(url)
        return True

    def fake_popen(cmd: list[str], **_kwargs: object) -> object:
        spawned.append(cmd)
        return object()

    msg = launch_grok_bot(opener=fake_open, popen=fake_popen, candidates=[binary, launcher])
    assert spawned == [[str(launcher)]]
    assert seen_urls == []
    assert "launch.sh" in msg
    assert "grok.com" not in msg


def test_electron_packaging_tree_is_untouched() -> None:
    """Companion must not replace the Electron grok-bot tree (PR #2 was reverted)."""
    repo = PKG.parent
    for relative in ("launch.sh", "install.sh", "uninstall.sh", "app/README.md"):
        assert (repo / relative).is_file(), relative
    app_readme = (repo / "app/README.md").read_text()
    assert "Electron" in app_readme
    assert "chrome-sandbox" in app_readme
    launch = (repo / "launch.sh").read_text()
    assert "chrome-sandbox" in launch
    assert "Electron" in launch


def test_gui_falls_back_to_x_ai_bot_not_grok_com() -> None:
    seen: list[str] = []

    def fake_open(url: str) -> bool:
        seen.append(url)
        return True

    msg = launch_grok_bot(opener=fake_open, candidates=[])
    assert seen == [GROK_BOT_URL]
    assert GROK_BOT_URL == "https://x.ai/bot"
    assert "grok.com" not in msg
    assert GROK_BOT_URL in msg


def test_gui_open_failure_is_one_line() -> None:
    def fake_open(url: str) -> bool:
        raise OSError("no display")

    msg = launch_grok_bot(opener=fake_open, candidates=[])
    assert "Could not open Grok Bot" in msg
    assert GROK_BOT_URL in msg
    assert "grok.com" not in msg


def test_commands_gui_clear_quit_help_notes() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    assert state.mode == "grok"
    assert handle_command("/gui", state).kind == "gui"
    state.notes.append("keep")
    state.messages.append({"role": "user", "content": "hi"})
    assert handle_command("/clear", state).kind == "clear"
    assert state.notes == []
    assert state.messages == [{"role": "system", "content": "sys"}]
    assert handle_command("/quit", state).kind == "quit"
    help_result = handle_command("/help", state)
    assert help_result is not None
    assert "Grok Bot companion" in help_result.message
    assert "/gui" in help_result.message
    assert "/grok" in help_result.message
    assert "/plan" in help_result.message
    assert "/sessions" in help_result.message
    assert "/chat" in help_result.message
    assert "Grok API (not Grok Bot)" in help_result.message
    assert "/send" not in help_result.message
    assert "x.ai/bot" in help_result.message
    assert "never grok.com" in help_result.message.lower()
    assert TITLE in help_result.message
    assert PANE_API in help_result.message
    assert handle_command("/notes", state).kind == "notes"
    assert handle_command("remember this", state) is None


def test_empty_enter_and_grok_launch_official_cli() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    empty = handle_command("", state)
    assert empty is not None
    assert empty.kind == "grok"
    assert empty.grok_args == ()
    launched = handle_command("/grok --help", state)
    assert launched.kind == "grok"
    assert launched.grok_args == ("--help",)


def test_chat_without_key_stays_on_grok() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    result = handle_command("/chat", state)
    assert result.kind == "need_key"
    assert "XAI_API_KEY" in result.message
    assert PANE_API in result.message
    assert "not Grok Bot" in result.message
    assert state.mode == "grok"


def test_chat_with_key_switches_and_can_send() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    assert state.mode == "grok"
    result = handle_command("/chat hello", state)
    assert result.kind == "chat"
    assert result.send_text == "hello"
    assert PANE_API in result.message
    assert handle_command("/notes", state).kind == "notes"
    assert state.mode == "notes"


def test_package_does_not_claim_to_be_grok_the_product() -> None:
    """Binary/help/README identify as grok-bot-tui companion around Grok Bot."""
    help_text = HELP + "\n" + build_parser().format_help()
    readme = (PKG / "README.md").read_text()
    init = (PKG / "src/grok_bot_tui/__init__.py").read_text()
    blob = "\n".join([help_text, readme, init])
    assert PROG in blob
    assert TITLE in blob
    assert STATUS in blob
    assert "Grok Bot companion" in blob
    assert "Grok GUI companion" not in blob
    assert "Grok terminal" not in blob
    assert "this TUI is Grok" not in blob.lower()
    assert "does not replace" in blob.lower() or "does **not** replace" in blob
    assert "https://x.ai/bot" in blob
    assert "launch.sh" in blob
    for path in (PKG / "src/grok_bot_tui").glob("*.py"):
        text = path.read_text()
        assert "Grok terminal" not in text
        assert "https://grok.com" not in text
