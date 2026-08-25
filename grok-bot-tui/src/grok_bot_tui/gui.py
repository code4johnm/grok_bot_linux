"""Launch packaged Grok Bot desktop via grok-bot / launch.sh. Never grok.com."""

from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path

# Official Grok Bot product page (https://x.ai/news/introducing-grok-bot).
GROK_BOT_URL = "https://x.ai/bot"


def _is_electron_binary(path: Path) -> bool:
    """True if this is the Electron grok-bot next to chrome-sandbox (not launch.sh)."""
    if path.name == "launch.sh":
        return False
    parent = path.parent
    return (parent / "chrome-sandbox").is_file() or (parent / "chrome_100_percent.pak").is_file()


def _launcher_candidates() -> list[Path]:
    """PATH wrapper and launch.sh — these apply chrome-sandbox / --no-sandbox."""
    names: list[Path] = []
    which = shutil.which("grok-bot")
    if which:
        names.append(Path(which))
    names.extend(
        [
            Path.home() / ".local/bin/grok-bot",
            Path("/usr/local/bin/grok-bot"),
            Path("/usr/bin/grok-bot"),
        ]
    )
    here = Path.cwd()
    for folder in [here, *here.parents]:
        names.append(folder / "launch.sh")
    names.extend(
        [
            Path.home() / ".local/opt/grok_bot_linux/launch.sh",
            Path("/usr/local/lib/grok-bot-linux/launch.sh"),
            Path("/usr/lib/grok-bot-linux/launch.sh"),
            Path("/usr/local/opt/grok_bot_linux/launch.sh"),
        ]
    )
    return names


def _electron_candidates() -> list[Path]:
    """Last resort: Electron binary in this repo's install prefix. Do not replace that tree."""
    names: list[Path] = []
    home = os.environ.get("GROK_BOT_HOME", "").strip()
    if home:
        names.append(Path(home) / "grok-bot")
    names.extend(
        [
            Path.cwd() / "app" / "grok-bot",
            Path.home() / ".local/opt/grok-bot/grok-bot",
            Path.home() / ".local/opt/Grok_Bot/grok-bot",
            Path("/opt/grok-bot/grok-bot"),
            Path("/opt/Grok_Bot/grok-bot"),
        ]
    )
    return names


def _desktop_candidates() -> list[Path]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in _launcher_candidates() + _electron_candidates():
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def find_desktop(candidates: Sequence[Path] | None = None) -> Path | None:
    """Prefer grok-bot wrapper / launch.sh over a raw Electron binary."""
    items = list(candidates) if candidates is not None else _desktop_candidates()
    usable = [path for path in items if path.is_file() and os.access(path, os.X_OK)]
    for path in usable:
        if not _is_electron_binary(path):
            return path
    return usable[0] if usable else None


def launch_grok_bot(
    *,
    opener: Callable[[str], bool] | None = None,
    popen: Callable[..., object] | None = None,
    candidates: Sequence[Path] | None = None,
) -> str:
    """Start packaged grok-bot / launch.sh; else https://x.ai/bot. Never grok.com."""
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
