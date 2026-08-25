"""Offline: non-interactive CLI (version/whoami/bots/status). No live SSO."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from grok_bot_tui import PROG, TITLE, __version__
from grok_bot_tui.config import load_config, write_default_config
from grok_bot_tui.cli import run_cli


def test_load_config_default_command() -> None:
    cfg = load_config([])
    assert cfg.command == "tui"
    assert cfg.json_out is False


def test_load_config_cli_command() -> None:
    cfg = load_config(["status"])
    assert cfg.command == "status"
    cfg = load_config(["--json", "bots"])
    assert cfg.command == "bots"
    assert cfg.json_out is True


def test_config_file_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("GROK_MODEL", raising=False)
    path = tmp_path / "config.json"
    monkeypatch.setenv("GROK_TUI_CONFIG", str(path))
    write_default_config(force=True)
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("grok-4.6", "grok-file-model"), encoding="utf-8")
    cfg = load_config([])
    assert cfg.model == "grok-file-model"
    cfg = load_config(["--model", "cli-model"])
    assert cfg.model == "cli-model"


def test_version_and_status_subprocess() -> None:
    env = os.environ.copy()
    env.pop("XAI_API_KEY", None)
    env.pop("GROK_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "grok_bot_tui", "version"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert TITLE in proc.stdout
    assert __version__ in proc.stdout
    assert "not Grok" in proc.stdout
    assert "https://grok.com" not in proc.stdout

    proc = subprocess.run(
        [sys.executable, "-m", "grok_bot_tui", "--json", "status"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["name"] == PROG
    assert payload["version"] == __version__
    assert "api_key" not in payload
    assert "token" not in json.dumps(payload)


def test_whoami_signed_out_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROK_BOT_TUI_HOME", str(tmp_path / "tui"))
    monkeypatch.setenv("GROK_BOT_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    cfg = load_config(["--json", "whoami"])
    code = run_cli(cfg)
    assert code == 1


def test_install_script_syntax() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "install.sh"
    assert script.is_file()
    proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    unit = root / "share" / "grok-tui-shell.service"
    assert unit.is_file()
    assert "tmux" in unit.read_text(encoding="utf-8")
    man = root / "share" / "man" / "man1" / "grok-tui-shell.1"
    assert man.is_file()
    assert "Raspberry Pi" in man.read_text(encoding="utf-8")
    req = (root / "requirements.txt").read_text(encoding="utf-8")
    assert "httpx" in req
    assert "prompt_toolkit" in req
