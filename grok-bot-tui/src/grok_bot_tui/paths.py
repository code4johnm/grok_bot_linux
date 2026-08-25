"""Operator-local config and data dirs. Never store secrets in data_dir."""

from __future__ import annotations

import os
from pathlib import Path


def tui_config_dir() -> Path:
    """XDG config for grok-tui-shell: $HOME/.config/grok-bot-tui/."""
    override = os.environ.get("GROK_TUI_CONFIG_DIR", "").strip()
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "grok-bot-tui"


def config_file_path() -> Path:
    override = os.environ.get("GROK_TUI_CONFIG", "").strip()
    if override:
        return Path(override)
    return tui_config_dir() / "config.json"


def data_dir(override: str | Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    env = os.environ.get("GROK_BOT_TUI_HOME", "").strip()
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg) / "grok-bot-tui"
    return Path.home() / ".grok-bot-tui"
