"""Non-interactive commands. Safe over SSH / headless Raspberry Pi. No secrets."""

from __future__ import annotations

import json
import platform
import sys

from grok_bot_tui import PROG, TITLE, __version__
from grok_bot_tui.config import Config
from grok_bot_tui.grok_bot_session import load_identity, session_bots
from grok_bot_tui.gui import desktop_supported, find_desktop, machine_arch


def run_cli(cfg: Config) -> int:
    command = cfg.command
    if command == "version":
        return _version(cfg)
    if command == "whoami":
        return _whoami(cfg)
    if command == "bots":
        return _bots(cfg)
    if command == "status":
        return _status(cfg)
    print(f"unknown command {command!r}. Try {PROG} --help.", file=sys.stderr)
    return 2


def _version(cfg: Config) -> int:
    if cfg.json_out:
        print(json.dumps({"name": PROG, "title": TITLE, "version": __version__}))
        return 0
    print(f"{TITLE} {__version__}")
    print("This is not Grok.")
    return 0


def _whoami(cfg: Config) -> int:
    ident = load_identity()
    payload = {
        "signed_in": ident.signed_in,
        "label": ident.label if ident.signed_in else "",
        "has_api_key": cfg.has_api_key,
    }
    if cfg.json_out:
        print(json.dumps(payload))
        return 0 if ident.signed_in or cfg.has_api_key else 1
    if ident.signed_in:
        print(f"signed in  {ident.label}")
        return 0
    if cfg.has_api_key:
        print("signed in  api.x.ai key (not Grok Bot SSO)")
        return 0
    print("signed out")
    return 1


def _bots(cfg: Config) -> int:
    ident = load_identity()
    rows = session_bots() if ident.signed_in else []
    safe = [{"id": r["id"], "name": r["name"], "blurb": r["blurb"]} for r in rows]
    if cfg.json_out:
        print(json.dumps({"signed_in": ident.signed_in, "bots": safe}))
        return 0 if safe else 1
    if not ident.signed_in:
        print("signed out. Open grok-bot, sign in (Gmail / Cursor SSO), then retry.")
        return 1
    if not safe:
        print("no bots in the Grok Bot cache yet. Open grok-bot, then retry.")
        return 1
    print(f"Bots  ({len(safe)} from signed-in Grok Bot)")
    for row in safe:
        print(f"{row['name']}\t{row['blurb']}")
    return 0


def _status(cfg: Config) -> int:
    ident = load_identity()
    arch = machine_arch() or platform.machine()
    desktop = desktop_supported(arch)
    found = find_desktop() if desktop else None
    bots = session_bots() if ident.signed_in else []
    payload = {
        "name": PROG,
        "title": TITLE,
        "version": __version__,
        "python": sys.version.split()[0],
        "arch": arch,
        "desktop_supported": desktop,
        "desktop_path": str(found) if found else "",
        "signed_in": ident.signed_in,
        "bot_count": len(bots),
        "has_api_key": cfg.has_api_key,
        "tty": bool(sys.stdin.isatty()),
    }
    if cfg.json_out:
        print(json.dumps(payload))
        return 0
    print(f"{TITLE} {__version__}")
    print(f"python: {payload['python']}")
    print(f"arch: {arch}")
    print(f"desktop: {'yes' if desktop else 'no (Electron grok-bot is x86_64 only)'}")
    if found:
        print(f"grok-bot: {found}")
    print(f"signed_in: {'yes' if ident.signed_in else 'no'}")
    print(f"bots: {len(bots)}")
    print(f"tty: {'yes' if payload['tty'] else 'no'}")
    print("This is not Grok.")
    return 0
