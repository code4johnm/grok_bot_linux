"""Command-line entry point for grok-bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from grok_bot import __version__
from grok_bot.client import GrokAPIError, send_prompt
from grok_bot.config import ConfigError, Settings, api_key_present, read_api_key
from grok_bot.daemon import Daemon, call_daemon, is_daemon_running
from grok_bot.workspace import Workspace, default_workspace_path


def _workspace(path: str | None) -> Workspace:
    return Workspace.open(Path(path) if path else default_workspace_path())


def cmd_ask(args: argparse.Namespace) -> int:
    prompt = args.prompt
    if prompt is None:
        prompt = sys.stdin.read()
    if not str(prompt).strip():
        print("error: prompt is empty (pass text or pipe stdin)", file=sys.stderr)
        return 2

    workspace = _workspace(args.workspace)
    settings = Settings.from_env()
    if args.model:
        settings = Settings(api_base=settings.api_base, model=args.model, timeout=settings.timeout)

    use_daemon = not args.direct and is_daemon_running(workspace)
    try:
        if use_daemon:
            response = call_daemon(workspace, {"cmd": "ask", "prompt": prompt}, timeout=settings.timeout)
            if not response.get("ok"):
                print(f"error: {response.get('error', 'daemon ask failed')}", file=sys.stderr)
                return 1
            reply = str(response["reply"])
        else:
            reply = send_prompt(prompt, read_api_key(), settings)
            workspace.append_history(prompt, reply)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except (GrokAPIError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(reply)
    if not reply.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    if is_daemon_running(workspace) and not args.force:
        print(f"error: daemon already running (pid {workspace.read_pid()})", file=sys.stderr)
        return 1
    try:
        read_api_key()
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    print(f"grok-bot daemon workspace={workspace.root}", file=sys.stderr)
    print(f"socket={workspace.socket_path}", file=sys.stderr)
    Daemon(workspace, Settings.from_env()).serve_forever()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    settings = Settings.from_env()
    running = is_daemon_running(workspace)
    print(f"version: {__version__}")
    print(f"workspace: {workspace.root}")
    print(f"daemon: {'running' if running else 'stopped'}")
    if running:
        print(f"pid: {workspace.read_pid()}")
        print(f"socket: {workspace.socket_path}")
    print(f"model: {settings.model}")
    print(f"api_base: {settings.api_base}")
    print(f"api_key: {'set' if api_key_present() else 'missing'}")
    print(f"history: {workspace.history_count()} entries")
    return 0


def cmd_version(_args: argparse.Namespace) -> int:
    print(__version__)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok-bot",
        description=(
            "Linux CLI and local daemon that send a prompt to the xAI Grok HTTP API "
            "and print the reply. Not an official xAI desktop application."
        ),
    )
    parser.add_argument(
        "--workspace",
        help="Workspace directory (default: $GROK_BOT_WORKSPACE or ~/.local/share/grok-bot)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="Send a prompt and print the assistant reply")
    ask.add_argument("prompt", nargs="?", help="Prompt text; omit to read stdin")
    ask.add_argument("--model", help="Override GROK_MODEL / default grok-4")
    ask.add_argument(
        "--direct",
        action="store_true",
        help="Call the API from this process even if the daemon is running",
    )
    ask.set_defaults(func=cmd_ask)

    daemon = sub.add_parser("daemon", help="Run the local Unix-socket daemon in the foreground")
    daemon.add_argument(
        "--force",
        action="store_true",
        help="Start even if a pid file is present (systemd restarts)",
    )
    daemon.set_defaults(func=cmd_daemon)

    status = sub.add_parser("status", help="Show workspace, daemon, and whether an API key is set")
    status.set_defaults(func=cmd_status)

    version = sub.add_parser("version", help="Print the grok-bot version")
    version.set_defaults(func=cmd_version)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
