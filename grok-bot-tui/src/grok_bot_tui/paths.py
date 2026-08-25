"""Operator-local data dir. Never store secrets here."""

from __future__ import annotations

import os
from pathlib import Path


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
