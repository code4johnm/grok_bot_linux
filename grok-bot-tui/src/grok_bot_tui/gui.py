"""Launch packaged grok-bot. Linux x86_64 community port, official macOS app."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

DESKTOP_ARCHES = frozenset({"x86_64", "amd64"})
OFFICIAL_ARCHES = frozenset({"x86_64", "amd64", "arm64", "aarch64"})
DESKTOP_X86_ONLY = (
    "grok-bot desktop is x86_64 only on Linux; there is no working desktop "
    "tarball for arm64. The official macOS app supports Apple Silicon. "
    "Chat still works."
)
MISSING_DESKTOP = (
    "grok-bot not found. Linux x86_64: ./install.sh "
    "(/opt/grok-bot/grok-bot or ~/.local/opt/grok-bot/grok-bot). "
    "macOS: ./scripts/install-macos.sh or /Applications/Grok Bot.app. "
    "Chat still works."
)


def machine_arch() -> str:
    return (os.environ.get("GROK_BOT_TUI_ARCH") or platform.machine() or "").strip()


def host_os() -> str:
    override = (os.environ.get("GROK_BOT_TUI_OS") or "").strip().lower()
    if override in {"macos", "darwin", "linux"}:
        if override == "darwin":
            return "macos"
        return override
    sysname = (platform.system() or "").lower()
    if sysname == "darwin":
        return "macos"
    return "linux"


def desktop_supported(arch: str | None = None, os_name: str | None = None) -> bool:
    os_name = (os_name or host_os()).lower()
    arch = (arch or machine_arch()).lower()
    if os_name in {"macos", "darwin"}:
        return arch in OFFICIAL_ARCHES
    return arch in DESKTOP_ARCHES


def _is_macos_app(path: Path) -> bool:
    return path.suffix == ".app" and path.is_dir() and (path / "Contents" / "MacOS").is_dir()


def _is_electron_binary(path: Path) -> bool:
    if path.name == "launch.sh":
        return False
    if _is_macos_app(path):
        return True
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
        names.append(Path(home))
    names.extend(
        [
            Path.cwd() / "app" / "grok-bot",
            Path.home() / ".local/opt/grok-bot/grok-bot",
            Path.home() / ".local/opt/Grok_Bot/grok-bot",
            Path("/opt/grok-bot/grok-bot"),
            Path("/opt/Grok_Bot/grok-bot"),
            Path("/Applications/Grok Bot.app"),
            Path.home() / "Applications" / "Grok Bot.app",
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


def _desktop_usable(path: Path) -> bool:
    if _is_macos_app(path):
        return True
    return path.is_file() and os.access(path, os.X_OK)


def find_desktop(candidates: Sequence[Path] | None = None) -> Path | None:
    items = list(candidates) if candidates is not None else _desktop_candidates()
    usable = [path for path in items if _desktop_usable(path)]
    for path in usable:
        if not _is_electron_binary(path):
            return path
    return usable[0] if usable else None


def find_electron(candidates: Sequence[Path] | None = None) -> Path | None:
    """Electron grok-bot binary (not launch.sh). Used to decrypt safeStorage."""
    items = list(candidates) if candidates is not None else _desktop_candidates()
    usable = [path for path in items if _desktop_usable(path)]
    for path in usable:
        if _is_electron_binary(path):
            return path
    return None


def _launch_argv(desktop: Path) -> list[str]:
    if _is_macos_app(desktop):
        return ["open", str(desktop)]
    return [str(desktop)]


def launch_grok_bot(
    *,
    popen: Callable[..., object] | None = None,
    candidates: Sequence[Path] | None = None,
    arch: str | None = None,
    os_name: str | None = None,
) -> str:
    """Start grok-bot / Grok Bot.app. Never open a browser for chat."""
    if not desktop_supported(arch, os_name):
        return DESKTOP_X86_ONLY
    desktop = find_desktop(candidates)
    if desktop is None:
        return MISSING_DESKTOP
    spawn = popen or subprocess.Popen
    argv = _launch_argv(desktop)
    try:
        spawn(argv, start_new_session=True)
    except OSError as exc:
        return f"Could not launch grok-bot ({desktop}): {exc}"
    return f"Launched grok-bot: {desktop}"
