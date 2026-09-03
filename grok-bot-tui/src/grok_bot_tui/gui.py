"""Launch packaged grok-bot on x86_64 and aarch64. Never open a browser."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

DESKTOP_ARCHES = frozenset({"x86_64", "amd64", "aarch64", "arm64"})
DESKTOP_UNSUPPORTED = (
    "grok-bot desktop needs x86_64 or aarch64; there is no desktop tarball "
    "for this architecture. Chat still works."
)
DESKTOP_X86_ONLY = DESKTOP_UNSUPPORTED
MISSING_DESKTOP = (
    "grok-bot not found. On x86_64 or aarch64 install with ./install.sh "
    "(PATH, /opt/grok-bot/grok-bot, or ~/.local/opt/grok-bot/grok-bot). "
    "Chat still works."
)


def machine_arch() -> str:
    return (os.environ.get("GROK_BOT_TUI_ARCH") or platform.machine() or "").strip()


def desktop_supported(arch: str | None = None) -> bool:
    return (arch or machine_arch()) in DESKTOP_ARCHES


def _is_electron_binary(path: Path) -> bool:
    if path.name == "launch.sh":
        return False
    parent = path.parent
    return (parent / "chrome-sandbox").is_file() or (parent / "chrome_100_percent.pak").is_file()


def _launcher_candidates() -> list[Path]:
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
        ]
    )
    return names


def _electron_candidates() -> list[Path]:
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
    items = list(candidates) if candidates is not None else _desktop_candidates()
    usable = [path for path in items if path.is_file() and os.access(path, os.X_OK)]
    for path in usable:
        if not _is_electron_binary(path):
            return path
    return usable[0] if usable else None


def find_electron(candidates: Sequence[Path] | None = None) -> Path | None:
    """Electron grok-bot binary (not launch.sh). Used to decrypt safeStorage."""
    items = list(candidates) if candidates is not None else _desktop_candidates()
    usable = [path for path in items if path.is_file() and os.access(path, os.X_OK)]
    for path in usable:
        if _is_electron_binary(path):
            return path
    return None


def launch_grok_bot(
    *,
    popen: Callable[..., object] | None = None,
    candidates: Sequence[Path] | None = None,
    arch: str | None = None,
) -> str:
    """Start packaged grok-bot / launch.sh on x86_64/aarch64. Never open a browser."""
    if not desktop_supported(arch):
        return DESKTOP_UNSUPPORTED
    desktop = find_desktop(candidates)
    if desktop is None:
        return MISSING_DESKTOP
    spawn = popen or subprocess.Popen
    try:
        spawn([str(desktop)], start_new_session=True)
    except OSError as exc:
        return f"Could not launch grok-bot ({desktop}): {exc}"
    return f"Launched grok-bot: {desktop}"
