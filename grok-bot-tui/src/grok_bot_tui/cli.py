"""Non-interactive commands. Safe over SSH / headless Raspberry Pi. No secrets."""

from __future__ import annotations

import json
import platform
import sys

from grok_bot_tui import PROG, TITLE, __version__
from grok_bot_tui.config import Config
from grok_bot_tui.grok_bot_auth import load_access_token
from grok_bot_tui.grok_bot_client import GrokBotAPIError, GrokBotClient
from grok_bot_tui.grok_bot_session import last_selected_agent_id, load_identity, session_bots
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
    if command == "chat":
        return _chat(cfg)
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
        print("signed out. Open grok-bot, sign in, then retry.")
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
    print(f"desktop: {'yes' if desktop else 'no (Electron grok-bot needs x86_64 or aarch64)'}")
    if found:
        print(f"grok-bot: {found}")
    print(f"signed_in: {'yes' if ident.signed_in else 'no'}")
    print(f"bots: {len(bots)}")
    print(f"tty: {'yes' if payload['tty'] else 'no'}")
    print("This is not Grok.")
    return 0


def _chat(cfg: Config) -> int:
    text = " ".join(cfg.words).strip()
    if not text:
        print(f"usage: {PROG} chat <message>", file=sys.stderr)
        print("Chat uses your Grok Bot session in this terminal. This is not Grok.", file=sys.stderr)
        return 2
    token = load_access_token()
    if not token:
        print(
            "Chat uses Grok Bot credentials, not an API key. "
            "Sign in with grok-bot, then retry.",
            file=sys.stderr,
        )
        return 2
    ident = load_identity()
    rows = session_bots() if ident.signed_in else []
    selected = last_selected_agent_id()
    pick = next((row for row in rows if row["id"] == selected), rows[0] if rows else None)
    if pick is None:
        print("No Grok Bot selected. Open grok-bot, then retry.", file=sys.stderr)
        return 1
    try:
        with GrokBotClient(token, timeout=min(cfg.timeout, 120.0)) as client:
            parts: list[str] = []
            for chunk in client.stream_text(
                [{"role": "user", "content": text}],
                agent_id=pick["id"],
                interval=0.4,
                timeout=min(cfg.timeout, 90.0),
            ):
                parts.append(chunk)
                if not cfg.json_out:
                    print(chunk, end="", flush=True)
            reply = "".join(parts)
    except GrokBotAPIError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if cfg.json_out:
        print(json.dumps({"bot": pick["name"], "text": reply}))
        return 0
    if reply and not reply.endswith("\n"):
        print()
    return 0
