"""Minimal one-thread TUI: header, transcript, compose. Optional /chat."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from grok_bot_tui import DEFAULT_BOT, PROG, __version__
from grok_bot_tui.client import GrokAPIError, GrokClient
from grok_bot_tui.config import Config, load_config
from grok_bot_tui.gui import launch_grok_bot
from grok_bot_tui.usage import append_usage_line

HELP = f"""{PROG}
One bot thread + compose. This is not Grok.

  <text>          Send chat (xAI Responses; needs XAI_API_KEY or GROK_API_KEY)
  /chat [text]    Same send
  /gui            Launch packaged grok-bot (x86_64). On arm64, desktop is x86_64-only.
  /bot <name>     Rename this thread (default {DEFAULT_BOT})
  /model [name]   Show or switch the /chat model
  /clear          Clear the transcript
  /help           Show this help
  /quit           Exit (also Ctrl+C or Ctrl+D)
"""


@dataclass
class SessionState:
    system: str
    model: str
    has_api: bool
    bot_name: str = DEFAULT_BOT
    messages: list[dict[str, str]] = field(default_factory=list)
    last_usage: dict[str, int] | None = None
    total_input: int = 0
    total_output: int = 0

    def __post_init__(self) -> None:
        if not self.messages:
            self.reset_messages()

    def reset_messages(self) -> None:
        self.messages = [{"role": "system", "content": self.system}]

    def clear_transcript(self) -> None:
        self.reset_messages()
        self.last_usage = None


@dataclass(frozen=True)
class CommandResult:
    kind: str
    message: str = ""
    send_text: str | None = None


def render_header(state: SessionState) -> str:
    return f"{state.bot_name}  ·  {PROG}"


def render_transcript(state: SessionState) -> str:
    lines: list[str] = []
    for item in state.messages:
        role = item.get("role")
        content = item.get("content") or ""
        if role == "user":
            lines.append(f"you: {content}")
        elif role == "assistant":
            lines.append(f"bot: {content}")
    return "\n".join(lines) if lines else "(no messages)"


def render_footer() -> str:
    return PROG


def render_screen(state: SessionState) -> str:
    return f"{render_header(state)}\n{render_transcript(state)}\n{render_footer()}"


def handle_command(line: str, state: SessionState) -> CommandResult:
    text = line.strip()
    if not text:
        return CommandResult("empty")

    if not text.startswith("/"):
        if not state.has_api:
            return CommandResult(
                "need_key",
                "No API key. Set XAI_API_KEY or GROK_API_KEY for /chat.",
            )
        return CommandResult("chat", send_text=text)

    cmd, *rest = text.split(maxsplit=1)
    name = cmd.lower()
    arg = rest[0].strip() if rest else ""

    if name in ("/quit", "/exit", "/q"):
        return CommandResult("quit")
    if name == "/help":
        return CommandResult("help", HELP.strip())
    if name == "/gui":
        return CommandResult("gui")
    if name == "/clear":
        state.clear_transcript()
        return CommandResult("clear", "Transcript cleared.")
    if name == "/bot":
        if not arg:
            return CommandResult("bot", f"Current bot: {state.bot_name}")
        state.bot_name = arg
        return CommandResult("bot", f"Thread: {state.bot_name}")
    if name == "/model":
        if arg:
            state.model = arg
            return CommandResult("model", f"/chat model set to {state.model}.")
        return CommandResult("model", f"/chat model: {state.model}")
    if name == "/chat":
        if not state.has_api:
            return CommandResult(
                "need_key",
                "No API key. Set XAI_API_KEY or GROK_API_KEY for /chat.",
            )
        if arg:
            return CommandResult("chat", send_text=arg)
        return CommandResult("chat", "Type a message to send.")
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def _toolbar(_state: SessionState) -> str:
    return PROG


def run_shell(
    cfg: Config,
    client: GrokClient | None,
    *,
    gui_popen: Callable[..., object] | None = None,
    gui_candidates: list[Path] | None = None,
    gui_arch: str | None = None,
) -> int:
    state = SessionState(system=cfg.system, model=cfg.model, has_api=cfg.has_api_key)
    session: PromptSession[str] = PromptSession(bottom_toolbar=lambda: _toolbar(state))
    print(render_header(state))
    print(f"{PROG} {__version__}. This is not Grok.")
    print(render_transcript(state))
    with patch_stdout():
        while True:
            try:
                line = session.prompt("compose> ")
            except (KeyboardInterrupt, EOFError):
                print()
                return 0

            result = handle_command(line, state)
            if result.kind == "quit":
                return 0
            if result.kind == "empty":
                continue
            if result.kind == "gui":
                print(
                    launch_grok_bot(
                        popen=gui_popen,
                        candidates=gui_candidates,
                        arch=gui_arch,
                    )
                )
                continue
            if result.message:
                print(result.message)
            if result.send_text:
                _send_chat(state, client, result.send_text)
    return 0


def _send_chat(state: SessionState, client: GrokClient | None, text: str) -> None:
    if client is None:
        print("No API key. Set XAI_API_KEY or GROK_API_KEY for /chat.")
        return
    state.messages.append({"role": "user", "content": text})
    print(f"you: {text}")
    print("bot: ", end="", flush=True)
    try:
        parts: list[str] = []
        for token in client.stream_text(state.messages):
            parts.append(token)
            print(token, end="", flush=True)
        print()
        reply = "".join(parts)
        if reply:
            state.messages.append({"role": "assistant", "content": reply})
        if client.last_usage is not None:
            state.last_usage = client.last_usage
            state.total_input += client.last_usage["input_tokens"]
            state.total_output += client.last_usage["output_tokens"]
            append_usage_line(client.last_usage, session=state.bot_name, model=state.model)
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
