"""Companion TUI: official Grok GUI launcher + local notes + optional API pane."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from grok_bot_tui import PROG, STATUS, TITLE, __version__
from grok_bot_tui.client import GrokAPIError, GrokClient
from grok_bot_tui.config import Config, load_config
from grok_bot_tui.gui import open_official_gui

HELP = f"""{TITLE}  ({PROG})
Status: {STATUS}. Work primarily in the official Grok GUI (/gui).
This shell is a companion — it is not Grok the product.

Commands:
  /gui            Open/focus the official Grok GUI in your browser
  /help           Show this help
  /clear          Clear the local pane (notes + API companion history)
  /notes          Local note buffer (always available)
  /chat [text]    API companion (not GUI) — needs XAI_API_KEY or GROK_API_KEY
  /quit           Exit (also Ctrl+C or Ctrl+D)
"""

PANE_API = "API companion (not GUI)"
PANE_NOTES = "local notes"


@dataclass
class SessionState:
    system: str
    model: str
    has_api: bool
    mode: str = "notes"
    notes: list[str] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.messages:
            self.reset_messages()
        if self.has_api:
            self.mode = "api"

    def reset_messages(self) -> None:
        self.messages = [{"role": "system", "content": self.system}]

    def clear_local(self) -> None:
        self.notes.clear()
        self.reset_messages()

    @property
    def pane_label(self) -> str:
        return PANE_API if self.mode == "api" else PANE_NOTES


@dataclass(frozen=True)
class CommandResult:
    kind: str
    message: str = ""
    send_text: str | None = None


def handle_command(line: str, state: SessionState) -> CommandResult | None:
    """Return a command result, or None if `line` is pane input (note or API)."""
    text = line.strip()
    if not text:
        return CommandResult("empty")
    if not text.startswith("/"):
        return None

    cmd, *rest = text.split(maxsplit=1)
    name = cmd.lower()
    arg = rest[0].strip() if rest else ""

    if name in ("/quit", "/exit", "/q"):
        return CommandResult("quit")
    if name == "/clear":
        state.clear_local()
        return CommandResult("clear", "Local pane cleared.")
    if name == "/help":
        return CommandResult("help", HELP.strip())
    if name == "/gui":
        return CommandResult("gui")
    if name == "/notes":
        state.mode = "notes"
        return CommandResult("notes", f"Local pane: {PANE_NOTES}.")
    if name == "/chat":
        if not state.has_api:
            return CommandResult(
                "need_key",
                "No API key. Local notes only. Set XAI_API_KEY or GROK_API_KEY for "
                f"{PANE_API}.",
            )
        state.mode = "api"
        if arg:
            return CommandResult("chat", f"Local pane: {PANE_API}.", send_text=arg)
        return CommandResult("chat", f"Local pane: {PANE_API}.")
    if name == "/model":
        if arg:
            state.model = arg
            return CommandResult("model", f"API companion model set to {state.model}.")
        return CommandResult("model", f"API companion model: {state.model}")
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def _toolbar(state: SessionState) -> str:
    return f" {PROG}  ·  {STATUS}  ·  {state.pane_label}  ·  /help /gui /clear /quit "


def run_shell(
    cfg: Config,
    client: GrokClient | None,
    *,
    gui_opener: Callable[[str], bool] | None = None,
) -> int:
    state = SessionState(system=cfg.system, model=cfg.model, has_api=cfg.has_api_key)
    session: PromptSession[str] = PromptSession(bottom_toolbar=lambda: _toolbar(state))
    print(f"{TITLE}  {PROG} {__version__}")
    print(f"{STATUS}. Official GUI: {cfg.gui_url}")
    print(f"Local pane: {state.pane_label}. Type /help for commands.")
    with patch_stdout():
        while True:
            try:
                prompt = "api> " if state.mode == "api" else "note> "
                line = session.prompt(prompt)
            except (KeyboardInterrupt, EOFError):
                print()
                return 0

            result = handle_command(line, state)
            send = None
            if result is not None:
                if result.kind == "quit":
                    return 0
                if result.kind == "empty":
                    continue
                if result.kind == "gui":
                    print(open_official_gui(cfg.gui_url, opener=gui_opener))
                    continue
                print(result.message)
                send = result.send_text
                if send is None:
                    continue
            else:
                send = line.strip()

            if state.mode == "notes" or client is None:
                state.notes.append(send)
                print(f"note: {send}")
                continue

            _send_api(state, client, send)
    return 0


def _send_api(state: SessionState, client: GrokClient, text: str) -> None:
    state.messages.append({"role": "user", "content": text})
    client.model = state.model
    print(f"{PANE_API}> ", end="", flush=True)
    try:
        parts: list[str] = []
        for token in client.stream_text(state.messages):
            parts.append(token)
            print(token, end="", flush=True)
        print()
        reply = "".join(parts)
        if reply:
            state.messages.append({"role": "assistant", "content": reply})
        else:
            print("(empty response)")
    except GrokAPIError as exc:
        print()
        print(f"error: {exc}")
        state.messages.pop()


def main(argv: list[str] | None = None) -> int:
    cfg = load_config(argv)
    client: GrokClient | None = None
    if cfg.has_api_key:
        assert cfg.api_key is not None
        client = GrokClient(
            api_key=cfg.api_key,
            model=cfg.model,
            timeout=cfg.timeout,
            base_url=cfg.base_url,
        )
    try:
        return run_shell(cfg, client)
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        if client is not None:
            client.close()
