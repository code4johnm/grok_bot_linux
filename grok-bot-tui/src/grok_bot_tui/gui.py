"""Launch Grok Bot desktop or https://x.ai/bot. Never grok.com."""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path

# Official Grok Bot product page (https://x.ai/news/introducing-grok-bot).
GROK_BOT_URL = "https://x.ai/bot"


def _desktop_candidates() -> list[Path]:
    names: list[Path] = []
    which = shutil.which("grok-bot")
    if which:
        names.append(Path(which))
    home = os.environ.get("GROK_BOT_HOME", "").strip()
    if home:
        names.append(Path(home) / "grok-bot")
    names.extend(
        [
            Path.home() / ".local/bin/grok-bot",
            Path.home() / ".local/opt/grok-bot/grok-bot",
            Path.home() / ".local/opt/Grok_Bot/grok-bot",
            Path("/usr/local/bin/grok-bot"),
            Path("/opt/grok-bot/grok-bot"),
            Path("/opt/Grok_Bot/grok-bot"),
        ]
    )
    return names


def find_desktop(candidates: Sequence[Path] | None = None) -> Path | None:
    for path in candidates if candidates is not None else _desktop_candidates():
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def launch_grok_bot(
    *,
    opener: Callable[[str], bool] | None = None,
    popen: Callable[..., object] | None = None,
    candidates: Sequence[Path] | None = None,
) -> str:
    """Prefer packaged grok-bot desktop; else open https://x.ai/bot. Never grok.com."""
    desktop = find_desktop(candidates)
    if desktop is not None:
        spawn = popen or subprocess.Popen
        try:
            spawn([str(desktop)], start_new_session=True)
        except OSError as exc:
            return f"Could not launch Grok Bot desktop ({desktop}): {exc}"
        return f"Launched Grok Bot desktop: {desktop}"

    open_url = opener or webbrowser.open
    try:
        ok = open_url(GROK_BOT_URL)
    except Exception as exc:  # noqa: BLE001 — one-line error, do not crash the TUI
        return f"Could not open Grok Bot ({GROK_BOT_URL}): {exc}"
    if ok is False:
        return f"Could not open Grok Bot ({GROK_BOT_URL}). Open it in a browser."
    return f"Opened Grok Bot: {GROK_BOT_URL}"
