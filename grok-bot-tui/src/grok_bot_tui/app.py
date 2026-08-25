"""Companion TUI: official Grok GUI launcher + local notes + optional API pane."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from grok_bot_tui import PROG, STATUS, TITLE, __version__
from grok_bot_tui.client import GrokAPIError, GrokClient
from grok_bot_tui.config import Config, load_config
from grok_bot_tui.gui import open_official_gui
from grok_bot_tui.paths import data_dir
from grok_bot_tui.prompts import PromptCatalog, PromptError, listing as prompt_listing
from grok_bot_tui.sessions import SessionStore, sanitize_name, timestamp_name
from grok_bot_tui.usage import append_audit_line, append_usage_line, format_meter

HELP = f"""{TITLE}  ({PROG})
Status: {STATUS}. Work primarily in the official Grok GUI (/gui).
This shell is a companion — it is not Grok the product.

Commands:
  /gui            Open/focus the official Grok GUI in your browser
  /help           Show this help
  /clear          Clear the local pane (does not delete saved sessions)
  /notes          Local note buffer (always available)
  /chat [text]    Immediate API companion (not GUI) turn (needs a key)
  /plan [text]    Hold the next API companion turn until y / /send (gated)
  /send           Approve the pending plan (also: y or /approve)
  /cancel         Drop the pending plan (also: n or /reject)
  /prompt         List official prompt ids (xai-org/grok-prompts)
  /prompt <id>    Fetch/cache that published prompt for later /chat
  /prompt off     Drop extra prompt; back to the default companion system
  /analyze <url>  Ask the API companion to explain a link (no X scrape)
  /model [name]   Show or switch the API companion model (default grok-4.6)
  /sessions       List saved local sessions
  /new [name]     Start a new local session
  /open <name>    Open a saved local session
  /forget [name]  Delete a saved session directory
  /quit           Exit (also Ctrl+C or Ctrl+D)
"""

PANE_API = "API companion (not GUI)"
PANE_NOTES = "local notes"
_HTTP_URL = re.compile(r"^https?://\S+$", re.IGNORECASE)


@dataclass
class SessionState:
    system: str
    model: str
    has_api: bool
    default_system: str = ""
    name: str = "default"
    prompt_id: str | None = None
    mode: str = "notes"
    notes: list[str] = field(default_factory=list)
    messages: list[dict[str, str]] = field(default_factory=list)
    last_usage: dict[str, int] | None = None
    total_input: int = 0
    total_output: int = 0
    pending_plan: str | None = None
    plans_approved: int = 0
    plans_cancelled: int = 0

    def __post_init__(self) -> None:
        if not self.default_system:
            self.default_system = self.system
        if not self.messages:
            self.reset_messages()
        if self.has_api:
            self.mode = "api"

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

    def reset_to_new(self, name: str) -> None:
        self.name = name
        self.notes.clear()
        self.prompt_id = None
        self.system = self.default_system
        self.last_usage = None
        self.total_input = 0
        self.total_output = 0
        self.pending_plan = None
        self.plans_approved = 0
        self.plans_cancelled = 0
        self.reset_messages()

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "prompt_id": self.prompt_id,
            "notes": list(self.notes),
            "messages": list(self.messages),
            "total_input": self.total_input,
            "total_output": self.total_output,
            "pending_plan": self.pending_plan,
            "plans_approved": self.plans_approved,
            "plans_cancelled": self.plans_cancelled,
        }

    def load_snapshot(self, data: dict) -> None:
        self.name = str(data.get("name") or self.name)
        if data.get("model"):
            self.model = str(data["model"])
        self.prompt_id = data.get("prompt_id") if isinstance(data.get("prompt_id"), str) else None
        self.notes = [str(n) for n in (data.get("notes") or [])]
        loaded = data.get("messages") or []
        self.messages = [
            {"role": m["role"], "content": m["content"]}
            for m in loaded
            if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant") and isinstance(m.get("content"), str)
        ]
        if not self.messages:
            self.reset_messages()
        else:
            sys_msg = self.messages[0]
            if sys_msg.get("role") == "system":
                self.system = sys_msg["content"]
        self.total_input = int(data.get("total_input") or 0)
        self.total_output = int(data.get("total_output") or 0)
        self.last_usage = None
        pending = data.get("pending_plan")
        self.pending_plan = pending if isinstance(pending, str) and pending else None
        self.plans_approved = int(data.get("plans_approved") or 0)
        self.plans_cancelled = int(data.get("plans_cancelled") or 0)

    @property
    def pane_label(self) -> str:
        return PANE_API if self.mode == "api" else PANE_NOTES


@dataclass(frozen=True)
class CommandResult:
    kind: str
    message: str = ""
    send_text: str | None = None


def analyze_request(url: str) -> str:
    """Local companion wording. Not a copy of AGPL grok_analyze_button.j2."""
    return (
        f"Explain this public link in short bullets: {url}\n"
        "Work from the URL text only. Do not claim you fetched or scraped the page."
    )


def handle_command(
    line: str,
    state: SessionState,
    prompts: PromptCatalog | None = None,
    sessions: SessionStore | None = None,
) -> CommandResult | None:
    """Return a command result, or None if `line` is pane input (note or API)."""
    text = line.strip()
    if not text:
        return CommandResult("empty")

    low = text.lower()
    if state.pending_plan and low in ("y", "/send", "/approve"):
        draft = state.pending_plan
        state.pending_plan = None
        state.plans_approved += 1
        return CommandResult("plan_send", "Plan approved.", send_text=draft)
    if state.pending_plan and low in ("n", "/cancel", "/reject"):
        state.pending_plan = None
        state.plans_cancelled += 1
        return CommandResult("plan_cancel", "Plan cancelled.")

    if not text.startswith("/"):
        if state.pending_plan:
            return CommandResult("pending", "Plan still held. y / n, /send, or /cancel.")
        return None

    cmd, *rest = text.split(maxsplit=1)
    name = cmd.lower()
    arg = rest[0].strip() if rest else ""

    if name in ("/send", "/approve"):
        return CommandResult("plan", "No pending plan.")
    if name in ("/cancel", "/reject"):
        return CommandResult("plan", "No pending plan.")
    if name == "/plan":
        return _handle_plan(state, arg)
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
            state.pending_plan = None
            return CommandResult("chat", f"Local pane: {PANE_API}.", send_text=arg)
        return CommandResult("chat", f"Local pane: {PANE_API}.")
    if name == "/model":
        if arg:
            state.model = arg
            return CommandResult("model", f"API companion model set to {state.model}.")
        return CommandResult("model", f"API companion model: {state.model}")
    if name == "/prompt":
        return _handle_prompt(state, arg, prompts)
    if name == "/analyze":
        return _handle_analyze(state, arg)
    if name == "/sessions":
        names = sessions.list_names() if sessions is not None else []
        listed = ", ".join(names) if names else "(none)"
        return CommandResult("sessions", f"Saved sessions: {listed}")
    if name == "/new":
        return _handle_new(state, arg, sessions)
    if name == "/open":
        return _handle_open(state, arg, sessions)
    if name == "/forget":
        return _handle_forget(state, arg, sessions)
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def _handle_prompt(state: SessionState, arg: str, prompts: PromptCatalog | None) -> CommandResult:
    if not arg:
        return CommandResult("prompt", prompt_listing())
    if arg.lower() in ("off", "none", "default"):
        state.apply_prompt(None, None)
        return CommandResult("prompt", "API companion prompt cleared (no extra official prompt).")
    catalog = prompts or PromptCatalog()
    try:
        text = catalog.get(arg)
    except PromptError as exc:
        return CommandResult("prompt", str(exc))
    state.apply_prompt(arg.lower(), text)
    return CommandResult(
        "prompt",
        f"Applied official prompt '{arg.lower()}' from xai-org/grok-prompts (cached locally).",
    )


def _handle_analyze(state: SessionState, arg: str) -> CommandResult:
    if not arg or not _HTTP_URL.match(arg):
        return CommandResult("analyze", "Usage: /analyze <http(s) url>. This shell does not scrape X.")
    if not state.has_api:
        state.notes.append(f"analyze: {arg}")
        return CommandResult(
            "need_key",
            f"No API key. Noted {arg}. Set XAI_API_KEY or GROK_API_KEY for {PANE_API}.",
        )
    state.mode = "api"
    state.pending_plan = None
    return CommandResult("analyze", f"{PANE_API} explain-link.", send_text=analyze_request(arg))


def _handle_plan(state: SessionState, arg: str) -> CommandResult:
    if not arg:
        if state.pending_plan:
            return CommandResult("plan", f"Pending plan: {state.pending_plan}")
        return CommandResult("plan", "Usage: /plan <text>  then y or /send.")
    if not state.has_api:
        return CommandResult(
            "need_key",
            "No API key. /plan is held only when XAI_API_KEY or GROK_API_KEY is set.",
        )
    state.pending_plan = arg
    return CommandResult("plan", "Plan held. y / /send to call the API companion, n / /cancel to drop.")


def _handle_new(state: SessionState, arg: str, sessions: SessionStore | None) -> CommandResult:
    if sessions is not None:
        sessions.save(state.snapshot())
    name = sanitize_name(arg) if arg else timestamp_name()
    if arg and name is None:
        return CommandResult("new", "Invalid session name. Use letters, digits, . _ -")
    assert name is not None
    state.reset_to_new(name)
    if sessions is not None:
        sessions.save(state.snapshot())
    return CommandResult("new", f"New session {state.name}.")


def _handle_open(state: SessionState, arg: str, sessions: SessionStore | None) -> CommandResult:
    if not arg or sessions is None:
        return CommandResult("open", "Usage: /open <name>")
    data = sessions.load(arg)
    if data is None:
        return CommandResult("open", f"No session named {arg}.")
    state.load_snapshot(data)
    return CommandResult("open", f"Opened session {state.name}.")


def _handle_forget(state: SessionState, arg: str, sessions: SessionStore | None) -> CommandResult:
    if sessions is None:
        return CommandResult("forget", "No session store.")
    target = arg or state.name
    if sessions.forget(target):
        return CommandResult("forget", f"Forgot session {target}.")
    return CommandResult("forget", f"No session named {target}.")


def _toolbar(state: SessionState) -> str:
    meter = format_meter(state.last_usage, state.total_input, state.total_output)
    pending = "pending plan · y/n" if state.pending_plan else ""
    bits = [PROG, STATUS, state.pane_label]
    if pending:
        bits.append(pending)
    if meter:
        bits.append(meter)
    bits.append("/help /gui /clear /quit")
    return "  ·  ".join(bits)


def run_shell(
    cfg: Config,
    client: GrokClient | None,
    *,
    gui_opener: Callable[[str], bool] | None = None,
    home: Path | None = None,
    prompts: PromptCatalog | None = None,
    sessions: SessionStore | None = None,
) -> int:
    root = Path(home) if home is not None else data_dir()
    catalog = prompts or PromptCatalog(cache_dir=root / "prompts")
    store = sessions or SessionStore(root / "sessions")
    usage_path = root / "usage.jsonl"
    state = SessionState(system=cfg.system, model=cfg.model, has_api=cfg.has_api_key)
    last = store.current_name()
    if last:
        restored = store.load(last)
        if restored is not None:
            state.load_snapshot(restored)
    session: PromptSession[str] = PromptSession(bottom_toolbar=lambda: _toolbar(state))
    print(f"{TITLE}  {PROG} {__version__}")
    print(f"{STATUS}. Official GUI: {cfg.gui_url}")
    print(f"Local pane: {state.pane_label}. Session {state.name}. Type /help for commands.")
    with patch_stdout():
        while True:
            try:
                prompt = "api> " if state.mode == "api" else "note> "
                line = session.prompt(prompt)
            except (KeyboardInterrupt, EOFError):
                print()
                store.save(state.snapshot())
                return 0

            result = handle_command(line, state, prompts=catalog, sessions=store)
            send = None
            if result is not None:
                if result.kind == "quit":
                    store.save(state.snapshot())
                    return 0
                if result.kind == "empty":
                    continue
                if result.kind == "gui":
                    print(open_official_gui(cfg.gui_url, opener=gui_opener))
                    continue
                print(result.message)
                send = result.send_text
                if result.kind == "plan_send":
                    append_audit_line("plan-approved", session=state.name, path=usage_path)
                elif result.kind == "plan_cancel":
                    append_audit_line("plan-cancelled", session=state.name, path=usage_path)
                store.save(state.snapshot())
                if send is None:
                    continue
            else:
                send = line.strip()

            if state.mode == "notes" or client is None:
                state.notes.append(send)
                print(f"note: {send}")
                store.save(state.snapshot())
                continue

            _send_api(state, client, send, usage_path)
            store.save(state.snapshot())
    return 0


def _send_api(state: SessionState, client: GrokClient, text: str, usage_path: Path) -> None:
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
        if client.last_usage is not None:
            state.last_usage = client.last_usage
            state.total_input += client.last_usage["input_tokens"]
            state.total_output += client.last_usage["output_tokens"]
            append_usage_line(
                client.last_usage,
                session=state.name,
                model=state.model,
                path=usage_path,
            )
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
