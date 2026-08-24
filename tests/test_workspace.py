from __future__ import annotations

from pathlib import Path

from grok_bot.workspace import Workspace, default_workspace_path


def test_default_uses_xdg(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("GROK_BOT_WORKSPACE", raising=False)
    assert default_workspace_path() == tmp_path / "xdg" / "grok-bot"


def test_override_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("GROK_BOT_WORKSPACE", str(tmp_path / "custom"))
    assert default_workspace_path() == tmp_path / "custom"


def test_open_creates_history(tmp_path) -> None:
    ws = Workspace.open(tmp_path / "ws")
    assert ws.root.is_dir()
    assert ws.history_path.is_file()
    ws.append_history("q", "a")
    assert ws.history_count() == 1
    line = ws.history_path.read_text(encoding="utf-8")
    assert "secret" not in line
    assert '"prompt": "q"' in line


def test_pid_roundtrip(tmp_path) -> None:
    ws = Workspace.open(tmp_path / "ws")
    assert ws.read_pid() is None
    ws.write_pid(4242)
    assert ws.read_pid() == 4242
    ws.clear_runtime_files()
    assert ws.read_pid() is None
    assert not Path(ws.socket_path).exists()
