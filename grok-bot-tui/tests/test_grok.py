"""Official grok CLI detection, --help flags, missing binary. Offline mocks only."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from grok_bot_tui.app import SessionState, _launch_official_grok, handle_command
from grok_bot_tui.grok import (
    DOCUMENTED_GROK_FLAGS,
    find_grok,
    flags_from_help,
    grok_help_text,
    missing_grok_message,
    run_grok,
    summarize_grok_home,
    validate_grok_args,
)
from grok_bot_tui.sessions import list_official_sessions


SAMPLE_HELP = """Grok Build TUI

Usage: grok [OPTIONS]

  --help            Show this message
  --agent TEXT
  --allow TEXT
  --deny TEXT
  --always-approve
  --continue
  --no-plan
  --no-subagents
  --model TEXT
"""


def test_grok_help_text_is_mocked() -> None:
    def runner(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert cmd == ["/opt/fake/grok", "--help"]
        return subprocess.CompletedProcess(cmd, 0, stdout=SAMPLE_HELP, stderr="")

    text = grok_help_text(Path("/opt/fake/grok"), runner=runner)
    assert "Grok Build TUI" in text
    allowed = flags_from_help(text)
    for flag in (
        "--help",
        "--agent",
        "--allow",
        "--deny",
        "--always-approve",
        "--continue",
        "--no-plan",
        "--no-subagents",
        "--model",
    ):
        assert flag in allowed


def test_flags_from_empty_help_use_documented_set_only() -> None:
    assert flags_from_help("") == set(DOCUMENTED_GROK_FLAGS)
    assert "--invented-queue" not in flags_from_help("")


def test_validate_rejects_invented_flags() -> None:
    allowed = flags_from_help(SAMPLE_HELP)
    assert validate_grok_args(["--help"], allowed) is None
    assert validate_grok_args(["--model", "grok-4"], allowed) is None
    err = validate_grok_args(["--invented-queue"], allowed)
    assert err is not None
    assert "--invented-queue" in err


def test_find_grok_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GROK_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "empty").mkdir()
    (tmp_path / "home").mkdir()
    assert find_grok() is None


def test_find_grok_home_bin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    grok = home / ".grok/bin/grok"
    grok.parent.mkdir(parents=True)
    grok.write_text("#!/bin/sh\n")
    grok.chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("GROK_BIN", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    assert find_grok() == grok


def test_missing_grok_message() -> None:
    msg = missing_grok_message()
    assert "Grok Build TUI" in msg
    assert "install-cli.sh" in msg or "x.ai/cli" in msg
    assert "~/.grok/bin/grok" in msg


def test_launch_without_binary_prints_missing(capsys: pytest.CaptureFixture[str]) -> None:
    _launch_official_grok(None, (), None)
    out = capsys.readouterr().out
    assert "Grok Build TUI" in out
    assert "not found" in out.lower() or "Install" in out


def test_run_grok_uses_injected_runner() -> None:
    seen: list[list[str]] = []

    def runner(cmd: list[str]) -> int:
        seen.append(cmd)
        return 0

    assert run_grok(Path("/opt/fake/grok"), ["--help"], runner=runner) == 0
    assert seen == [["/opt/fake/grok", "--help"]]


def test_plan_maps_to_official_grok_not_fake_queue() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    allowed = flags_from_help(SAMPLE_HELP)
    result = handle_command("/plan", state, allowed_flags=allowed)
    assert result.kind == "grok"
    assert result.grok_args == ()
    assert result.send_text is None
    assert "--no-plan" not in (result.grok_args or ())
    rejected = handle_command("/plan --no-plan", state, allowed_flags=allowed)
    assert rejected.kind == "grok_error"
    assert "--no-plan" in rejected.message


def test_grok_command_rejects_unknown_flag() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    result = handle_command("/grok --invented", state, allowed_flags=flags_from_help(SAMPLE_HELP))
    assert result.kind == "grok_error"
    assert "--invented" in result.message


def test_sessions_are_readonly_official_home(tmp_path: Path) -> None:
    home = tmp_path / ".grok"
    home.mkdir()
    (home / "auth.json").write_text('{"token":"secret-value"}')
    (home / "sessions").mkdir()
    (home / "notes.txt").write_text("ok")
    text = list_official_sessions(home)
    assert "auth.json" in text
    assert "skipped" in text
    assert "secret-value" not in text
    assert "sessions/" in text
    assert summarize_grok_home(home) == text
    missing = summarize_grok_home(tmp_path / "nope")
    assert "No ~/.grok" in missing or "not" in missing.lower()
