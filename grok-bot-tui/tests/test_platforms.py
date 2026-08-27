"""Offline: official macOS variant + Linux port version pin. No live downloads."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from grok_bot_tui.gui import desktop_supported, find_electron, launch_grok_bot
from grok_bot_tui.grok_bot_session import config_dir, data_dir

REPO = Path(__file__).resolve().parents[2]
PKG = Path(__file__).resolve().parents[1]


def test_platforms_catalog() -> None:
    catalog = json.loads((REPO / "share" / "platforms.json").read_text(encoding="utf-8"))
    assert catalog["internal_app"] == "sand"
    assert catalog["desktop_version"] == "0.27.0"
    assert "{version}" in catalog["macos"]["arm64"]["dmg"]
    assert "ios" not in catalog
    assert "windows" not in catalog
    pin = (REPO / "VERSION").read_text(encoding="utf-8").strip()
    assert pin == "0.27.0"


def test_install_scripts_exist_and_parse() -> None:
    for name in (
        "install-macos.sh",
        "download-official.sh",
        "check-official.sh",
        "install-for.sh",
        "common.sh",
    ):
        script = REPO / "scripts" / name
        assert script.is_file(), name
        proc = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
    assert not (REPO / "scripts" / "install-ios.sh").exists()
    assert not (REPO / "scripts" / "install-windows.sh").exists()


def test_macos_named_urls() -> None:
    proc = subprocess.run(
        [
            "bash",
            "-c",
            "ROOT=\"$1\"; source \"$ROOT/scripts/common.sh\"; "
            "macos_dmg_url arm64 0.27.0; "
            "macos_dmg_url x64 0.27.0",
            "helper",
            str(REPO),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    assert lines[0].endswith("/Grok_Bot_0.27.0.dmg")
    assert "darwin-arm64/0.27.0" in lines[0]
    assert lines[1].endswith("/Grok_Bot_0.27.0_x64.dmg")


def test_install_for_help_lists_macos() -> None:
    proc = subprocess.run(
        ["bash", str(REPO / "scripts" / "install-for.sh"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "macos" in proc.stdout
    assert "windows" not in proc.stdout
    assert "ios" not in proc.stdout


def test_desktop_supported_macos() -> None:
    assert desktop_supported("x86_64", "linux") is True
    assert desktop_supported("aarch64", "linux") is False
    assert desktop_supported("arm64", "macos") is True
    assert desktop_supported("x86_64", "macos") is True
    assert desktop_supported("arm64", "windows") is False


def test_macos_app_launch(tmp_path: Path) -> None:
    app = tmp_path / "Grok Bot.app"
    (app / "Contents" / "MacOS").mkdir(parents=True)
    (app / "Contents" / "MacOS" / "Grok Bot").write_text("", encoding="utf-8")
    spawned: list[list[str]] = []

    def fake_popen(cmd: list[str], **_kwargs: object) -> object:
        spawned.append(cmd)
        return object()

    msg = launch_grok_bot(popen=fake_popen, candidates=[app], arch="arm64", os_name="macos")
    assert spawned == [["open", str(app)]]
    assert "Launched grok-bot" in msg
    assert find_electron(candidates=[app]) == app


def test_session_dirs_macos(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROK_BOT_TUI_OS", "macos")
    monkeypatch.delenv("GROK_BOT_CONFIG", raising=False)
    monkeypatch.delenv("GROK_BOT_DATA", raising=False)
    monkeypatch.setenv("GROK_BOT_CONFIG", str(tmp_path / "Grok Bot"))
    assert config_dir() == tmp_path / "Grok Bot"
    assert data_dir() == tmp_path / "Grok Bot"


def test_readme_mentions_macos_not_ios_windows() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "install-macos.sh" in text
    assert "0.27.0" in text
    assert "install-windows.sh" not in text
    assert "install-ios.sh" not in text
    tui = (PKG / "README.md").read_text(encoding="utf-8")
    assert "install-macos.sh" in tui
    assert "Application Support" in tui
    assert "install-windows.sh" not in tui
    assert "install-ios.sh" not in tui
