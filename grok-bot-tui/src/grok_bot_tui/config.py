"""CLI flags, config.json, optional /chat (xAI Responses). Never logs secrets."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grok_bot_tui import PROG, TITLE
from grok_bot_tui.paths import config_file_path, tui_config_dir

DEFAULT_MODEL = "grok-4.6"
DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_SYSTEM = "You are a short, helpful chat in Grok GUI TUI shell. This is not Grok."
DEFAULT_TIMEOUT = 3600.0
CLI_COMMANDS = ("tui", "version", "whoami", "bots", "status")


@dataclass(frozen=True)
class Config:
    api_key: str | None
    model: str
    system: str
    timeout: float
    base_url: str
    command: str = "tui"
    json_out: bool = False

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _parse_timeout(raw: str | None, fallback: float) -> float:
    if raw is None or raw.strip() == "":
        return fallback
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid timeout: {raw!r}") from exc
    if timeout <= 0:
        raise SystemExit("Timeout must be greater than 0.")
    return timeout


def load_file_config(path: Path | None = None) -> dict[str, Any]:
    dest = path or config_file_path()
    if not dest.is_file():
        return {}
    try:
        raw = json.loads(dest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def default_file_config() -> dict[str, Any]:
    return {
        "model": DEFAULT_MODEL,
        "base_url": DEFAULT_BASE_URL,
        "timeout": DEFAULT_TIMEOUT,
        "system": DEFAULT_SYSTEM,
    }


def write_default_config(*, force: bool = False) -> Path:
    """Create ~/.config/grok-bot-tui/config.json if missing. No secrets."""
    dest = config_file_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and not force:
        return dest
    dest.write_text(json.dumps(default_file_config(), indent=2) + "\n", encoding="utf-8")
    try:
        os.chmod(dest, 0o644)
    except OSError:
        pass
    return dest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            f"{TITLE} — companion TUI for Grok Bot (the Electron GUI). "
            "/login launches grok-bot and prints Cursor SSO (OSC 8). "
            "/gui launches packaged grok-bot on x86_64. "
            "Commands: tui (default), version, whoami, bots, status. "
            "This is not Grok."
        ),
        epilog="TUI slash commands: /login /logout /whoami /agents /chat /gui /help /quit",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="xAI API key for /chat (XAI_API_KEY or GROK_API_KEY).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"/chat model ID (default: {DEFAULT_MODEL} or GROK_MODEL).",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="/chat system prompt (default: GROK_SYSTEM).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help=f"HTTP timeout for /chat (default: {DEFAULT_TIMEOUT:g} or GROK_TIMEOUT).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"xAI Responses base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--json",
        dest="json_out",
        action="store_true",
        help="JSON output for non-interactive commands (bots, whoami, status).",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="tui",
        choices=CLI_COMMANDS,
        help="tui (interactive, default) or a non-interactive command.",
    )
    return parser


def load_config(argv: list[str] | None = None) -> Config:
    args = build_parser().parse_args(argv)
    file_cfg = load_file_config()
    api_key = (args.api_key or "").strip() or _first_env("XAI_API_KEY", "GROK_API_KEY")

    timeout = args.timeout
    if timeout is None:
        file_timeout = file_cfg.get("timeout")
        if isinstance(file_timeout, (int, float)) and float(file_timeout) > 0:
            timeout = float(file_timeout)
        else:
            timeout = _parse_timeout(os.environ.get("GROK_TIMEOUT"), DEFAULT_TIMEOUT)
    elif timeout <= 0:
        raise SystemExit("Timeout must be greater than 0.")

    file_model = str(file_cfg.get("model") or "").strip()
    file_system = file_cfg.get("system")
    file_base = str(file_cfg.get("base_url") or "").strip()

    return Config(
        api_key=api_key,
        model=(args.model or _first_env("GROK_MODEL") or file_model or DEFAULT_MODEL),
        system=(
            args.system
            if args.system is not None
            else (_first_env("GROK_SYSTEM") or (str(file_system) if file_system else None) or DEFAULT_SYSTEM)
        ),
        timeout=timeout,
        base_url=(args.base_url or _first_env("GROK_BASE_URL") or file_base or DEFAULT_BASE_URL).rstrip("/"),
        command=str(args.command or "tui"),
        json_out=bool(args.json_out),
    )


# Re-export for callers that create the config dir during install.
__all__ = [
    "CLI_COMMANDS",
    "Config",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_SYSTEM",
    "DEFAULT_TIMEOUT",
    "build_parser",
    "config_file_path",
    "default_file_config",
    "load_config",
    "load_file_config",
    "tui_config_dir",
    "write_default_config",
]
