"""Read-only view of official ~/.grok metadata. Never write auth or credentials."""

from __future__ import annotations

from pathlib import Path

from grok_bot_tui.grok import summarize_grok_home


def list_official_sessions(root: Path | None = None) -> str:
    return summarize_grok_home(root)
