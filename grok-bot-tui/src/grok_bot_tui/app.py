"""Companion TUI around Grok Bot: grok-bot desktop + official grok CLI."""

from __future__ import annotations

import shlex
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from grok_bot_tui import PROG, STATUS, TITLE, __version__
from grok_bot_tui.client import GrokAPIError, GrokClient
from grok_bot_tui.config import Config, load_config
from grok_bot_tui.grok import (
    find_grok,
    flags_from_help,
    grok_help_text,
    missing_grok_message,
    run_grok,
    summarize_grok_home,
    validate_grok_args,
)
from grok_bot_tui.gui import GROK_BOT_URL, launch_grok_bot
from grok_bot_tui.prompts import PromptCatalog, PromptError, listing as prompt_listing
from grok_bot_tui.usage import append_usage_line, format_meter

HELP = f"""{TITLE}  ({PROG})
Status: {STATUS}. This wraps Grok Bot, not Grok the chat app at grok.com.

Default: official grok CLI (Grok Build TUI). Empty Enter or /grok launches it.
/gui starts packaged grok-bot or launch.sh (chrome-sandbox), else {GROK_BOT_URL}.
Never grok.com. This TUI does not replace the Electron grok-bot tree.

Commands:
  /gui            Launch grok-bot / launch.sh, else {GROK_BOT_URL}
  /grok [flags]   Run official grok (flags from grok --help only)
  Enter           Same as /grok with no extra flags
  /plan [flags]   Launch grok in official plan mode (omit --no-plan)
  /help           Show this help
  /clear          Clear the local scratch notes
  /notes          Local scratch (not Grok Bot state)
  /sessions       Read-only summary of official ~/.grok (skips credentials)
  /chat [text]    Optional Grok API (not Grok Bot) — needs a key
  /prompt         Optional Grok API prompt catalog (xai-org/grok-prompts)
  /analyze <url>  Optional Grok API explain-link (no X scrape)
  /model [name]   Optional Grok API model (default grok-4.6)
  /quit           Exit (also Ctrl+C or Ctrl+D)
"""

PANE_API = "Grok API (not Grok Bot)"
PANE_NOTES = "local scratch"
PANE_GROK = "official grok CLI"


@dataclass
class SessionState:
    system: str
    model: str
    has_api: bool
    default_system: str = ""
    mode: str = "grok"
    notes: list[str] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)
    last_usage: dict[str, int] | None = None
    total_input: int = 0
    total_output: int = 0
    prompt_id: str | None = None

    def __post_init__(self) -> None:
        if not self.default_system:
            self.default_system = self.system
        if not self.messages:
            self.reset_messages()

    def reset_messages(self) -> None:
        self.messages = [{"role": "system", "content": self.system}]

    def clear_local(self) -> None:
        self.notes.clear()
        self.reset_messages()

    def apply_prompt(self, prompt_id: str | None, text: str | None) -> None:
        if prompt_id is None or text is None:
            self.prompt_id = None
            self.system = self.default_system
        else:
            self.prompt_id = prompt_id
            self.system = text
        self.reset_messages()

    @property
    def pane_label(self) -> str:
        if self.mode == "api":
            return PANE_API
        if self.mode == "notes":
            return PANE_NOTES
        return PANE_GROK


@dataclass(frozen=True)
class CommandResult:
    kind: str
    message: str = ""
    send_text: str | None = None
    grok_args: tuple[str, ...] | None = None


def analyze_request(url: str) -> str:
    return (
        f"Explain this public link in short bullets: {url}\n"
        "Work from the URL text only. Do not claim you fetched or scraped the page."
    )


def handle_command(
    line: str,
    state: SessionState,
    prompts: PromptCatalog | None = None,
    allowed_flags: set[str] | None = None,
) -> CommandResult | None:
    text = line.strip()
    if not text:
        return CommandResult("grok", grok_args=())

    if text.startswith("-"):
        err = validate_grok_args(shlex.split(text), allowed_flags or flags_from_help(""))
        if err:
            return CommandResult("grok_error", err)
        return CommandResult("grok", grok_args=tuple(shlex.split(text)))

    if not text.startswith("/"):
        return None

    cmd, *rest = text.split(maxsplit=1)
    name = cmd.lower()
    arg = rest[0].strip() if rest else ""

    if name in ("/quit", "/exit", "/q"):
        return CommandResult("quit")
    if name == "/clear":
        state.clear_local()
        return CommandResult("clear", "Local scratch cleared.")
    if name == "/help":
        return CommandResult("help", HELP.strip())
    if name == "/gui":
        return CommandResult("gui")
    if name == "/notes":
        state.mode = "notes"
        return CommandResult("notes", f"Local pane: {PANE_NOTES} (not Grok Bot state).")
    if name == "/grok":
        return _grok_args_result(arg, allowed_flags, plan=False)
    if name == "/plan":
        return _grok_args_result(arg, allowed_flags, plan=True)
    if name == "/sessions":
        return CommandResult("sessions")
    if name == "/chat":
        if not state.has_api:
            return CommandResult(
                "need_key",
                "No API key. /chat is optional Grok API (not Grok Bot). "
                "Set XAI_API_KEY or GROK_API_KEY.",
            )
        state.mode = "api"
        if arg:
            return CommandResult("chat", f"Local pane: {PANE_API}.", send_text=arg)
        return CommandResult("chat", f"Local pane: {PANE_API}.")
    if name == "/model":
        if arg:
            state.model = arg
            return CommandResult("model", f"{PANE_API} model set to {state.model}.")
        return CommandResult("model", f"{PANE_API} model: {state.model}")
    if name == "/prompt":
        return _handle_prompt(state, arg, prompts)
    if name == "/analyze":
        return _handle_analyze(state, arg)
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def _grok_args_result(arg: str, allowed: set[str] | None, *, plan: bool) -> CommandResult:
    try:
        args = shlex.split(arg) if arg else []
    except ValueError:
        return CommandResult("grok_error", "Could not parse grok arguments.")
    if plan and "--no-plan" in args:
        return CommandResult(
            "grok_error",
            "/plan is official grok plan mode. Drop --no-plan (that flag disables plan).",
        )
    err = validate_grok_args(args, allowed or flags_from_help(""))
    if err:
        return CommandResult("grok_error", err)
    label = "Launching official grok (plan mode)." if plan else "Launching official grok (Grok Build TUI)."
    return CommandResult("grok", label, grok_args=tuple(args))


def _handle_prompt(state: SessionState, arg: str, prompts: PromptCatalog | None) -> CommandResult:
    if not arg:
        return CommandResult("prompt", prompt_listing())
    if arg.lower() in ("off", "none", "default"):
        state.apply_prompt(None, None)
        return CommandResult("prompt", f"{PANE_API} prompt cleared.")
    catalog = prompts or PromptCatalog()
    try:
        text = catalog.get(arg)
    except PromptError as exc:
        return CommandResult("prompt", str(exc))
    state.apply_prompt(arg.lower(), text)
    return CommandResult("prompt", f"{PANE_API} applied official prompt '{arg.lower()}' (cached).")


def _handle_analyze(state: SessionState, arg: str) -> CommandResult:
    if not arg or not (arg.startswith("http://") or arg.startswith("https://")):
        return CommandResult("analyze", "Usage: /analyze <http(s) url>. This shell does not scrape X.")
    if not state.has_api:
        state.notes.append(f"analyze: {arg}")
        return CommandResult(
            "need_key",
            f"No API key. Noted {arg}. /analyze uses {PANE_API} only. "
            "Set XAI_API_KEY or GROK_API_KEY.",
        )
    state.mode = "api"
    return CommandResult("analyze", f"{PANE_API} explain-link.", send_text=analyze_request(arg))


def _toolbar(state: SessionState) -> str:
    meter = format_meter(state.last_usage, state.total_input, state.total_output)
    bits = [PROG, STATUS, state.pane_label]
    if meter:
        bits.append(meter)
    bits.append("/help /gui /grok /quit")
    return "  ·  ".join(bits)


def run_shell(
    cfg: Config,
    client: GrokClient | None,
    *,
    grok_bin: Path | None = None,
    grok_help: str | None = None,
    grok_runner: Callable[[Sequence[str]], int] | None = None,
    gui_opener: Callable[[str], bool] | None = None,
    gui_popen: Callable[..., object] | None = None,
    grok_home: Path | None = None,
    prompts: PromptCatalog | None = None,
) -> int:
    binary = grok_bin if grok_bin is not None else find_grok()
    allowed = flags_from_help(grok_help or "")
    if binary is not None and grok_help is None:
        try:
            allowed = flags_from_help(grok_help_text(binary))
        except RuntimeError:
            allowed = flags_from_help("")

    state = SessionState(system=cfg.system, model=cfg.model, has_api=cfg.has_api_key)
    session: PromptSession[str] = PromptSession(bottom_toolbar=lambda: _toolbar(state))
    print(f"{TITLE}  {PROG} {__version__}")
    print(f"{STATUS}. /gui → grok-bot/launch.sh or {GROK_BOT_URL}. Default: official grok CLI.")
    print(f"Local pane: {state.pane_label}. Type /help for commands.")
    with patch_stdout():
        while True:
            try:
                prompt = "api> " if state.mode == "api" else "grok> "
                if state.mode == "notes":
                    prompt = "note> "
                line = session.prompt(prompt)
            except (KeyboardInterrupt, EOFError):
                print()
                return 0

            result = handle_command(line, state, prompts=prompts, allowed_flags=allowed)
            if result is None:
                state.notes.append(line.strip())
                print(f"note: {line.strip()}  (Enter or /grok launches Grok Build TUI)")
                continue
            if result.kind == "quit":
                return 0
            if result.kind == "gui":
                print(launch_grok_bot(opener=gui_opener, popen=gui_popen))
                continue
            if result.kind == "sessions":
                print(summarize_grok_home(grok_home))
                continue
            if result.kind == "grok":
                _launch_official_grok(binary, result.grok_args or (), grok_runner)
                continue
            if result.message:
                print(result.message)
            if result.send_text and client is not None:
                _send_api(state, client, result.send_text)
    return 0


def _launch_official_grok(
    binary: Path | None,
    args: Sequence[str],
    runner: Callable[[Sequence[str]], int] | None,
) -> None:
    if binary is None:
        print(missing_grok_message())
        return
    print(f"Running {binary} {' '.join(args)}".rstrip())
    code = run_grok(binary, args, runner=runner)
    if code:
        print(f"grok exited {code}")


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
        if client.last_usage is not None:
            state.last_usage = client.last_usage
            state.total_input += client.last_usage["input_tokens"]
            state.total_output += client.last_usage["output_tokens"]
            append_usage_line(client.last_usage, session="api-chat", model=state.model)
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
