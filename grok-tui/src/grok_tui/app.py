"""Keyboard-only chat loop: one transcript, one input, in-memory history."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from grok_tui import __version__
from grok_tui.client import GrokAPIError, GrokClient
from grok_tui.config import Config, MissingAPIKeyError, load_config

HELP = """Commands:
  /help           Show this help
  /clear          Clear in-memory history (keeps the system prompt)
  /model [id]     Show or set the model for the rest of this session
  /quit           Exit (also Ctrl+C or Ctrl+D)
"""


@dataclass
class ChatState:
    system: str
    model: str
    messages: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.messages:
            self.reset()

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": self.system}]


@dataclass(frozen=True)
class CommandResult:
    kind: str
    message: str = ""


def handle_command(line: str, state: ChatState) -> CommandResult | None:
    """Return a command result, or None if `line` should be sent to the model."""
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
        state.reset()
        return CommandResult("clear", "History cleared.")
    if name == "/help":
        return CommandResult("help", HELP.strip())
    if name == "/model":
        if arg:
            state.model = arg
            return CommandResult("model", f"Model set to {state.model}.")
        return CommandResult("model", f"Model: {state.model}")
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def run_chat(cfg: Config, client: GrokClient) -> int:
    state = ChatState(system=cfg.system, model=cfg.model)
    session: PromptSession[str] = PromptSession()
    print(f"grok-tui {__version__}  model={state.model}")
    print("In-memory session. Type /help for commands.")
    with patch_stdout():
        while True:
            try:
                line = session.prompt("you> ")
            except (KeyboardInterrupt, EOFError):
                print()
                return 0

            result = handle_command(line, state)
            if result is not None:
                if result.kind == "quit":
                    return 0
                if result.kind == "empty":
                    continue
                print(result.message)
                continue

            state.messages.append({"role": "user", "content": line.strip()})
            client.model = state.model
            print("grok> ", end="", flush=True)
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
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        cfg = load_config(argv)
    except MissingAPIKeyError as exc:
        print(exc, file=sys.stderr)
        return 1

    with GrokClient(
        api_key=cfg.api_key,
        model=cfg.model,
        timeout=cfg.timeout,
        base_url=cfg.base_url,
    ) as client:
        try:
            return run_chat(cfg, client)
        except KeyboardInterrupt:
            print()
            return 0
