"""Grok GUI TUI shell: sign-in, agent picker, one chat thread."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from grok_bot_tui import PROG, TITLE, __version__
from grok_bot_tui.agents import Agent, AgentCatalog
from grok_bot_tui.auth import (
    CONSOLE_KEYS_URL,
    CredentialStore,
    LoopbackCatcher,
    SignInLink,
    mask_secret,
    open_browser,
    signin_url,
)
from grok_bot_tui.client import GrokAPIError, GrokClient
from grok_bot_tui.config import Config, load_config
from grok_bot_tui.gui import launch_grok_bot
from grok_bot_tui.pixel import sprite_column
from grok_bot_tui.usage import append_usage_line

HELP = f"""{TITLE}
Companion TUI for the Grok GUI. This is not Grok.

  /login          Sign in (browser link + paste key, or XAI_API_KEY)
  /logout         Forget stored credentials
  /whoami         Show truncated account/key label
  /agents         Refresh agent/model list
  j / k  or ↑↓    Move selection (agent list)
  Enter           Use selected agent for chat
  <text>          Send chat to the active agent
  /gui            Launch packaged grok-bot desktop (x86_64)
  /clear          Clear the transcript
  /help           Show this help
  /quit           Exit
"""


@dataclass
class SessionState:
    system: str
    model: str
    has_api: bool
    bot_name: str = "shell"
    auth_state: str = "signed_out"
    auth_label: str = ""
    auth_error: str = ""
    agents: list[Agent] = field(default_factory=list)
    agent_index: int = 0
    view: str = "sign_in"
    messages: list[dict[str, str]] = field(default_factory=list)
    last_usage: dict[str, int] | None = None
    total_input: int = 0
    total_output: int = 0

    def __post_init__(self) -> None:
        if not self.messages:
            self.reset_messages()
        if self.has_api:
            self.auth_state = "signed_in"
            self.view = "agents"

    def reset_messages(self) -> None:
        self.messages = [{"role": "system", "content": self.system}]

    def clear_transcript(self) -> None:
        self.reset_messages()
        self.last_usage = None

    @property
    def active_agent(self) -> Agent | None:
        if not self.agents:
            return None
        idx = max(0, min(self.agent_index, len(self.agents) - 1))
        return self.agents[idx]


@dataclass(frozen=True)
class CommandResult:
    kind: str
    message: str = ""
    send_text: str | None = None


def render_header(state: SessionState) -> str:
    return TITLE


def render_footer(state: SessionState) -> str:
    agent = state.active_agent.name if state.active_agent else "-"
    auth = "signed in" if state.auth_state == "signed_in" else state.auth_state.replace("_", " ")
    return f"agent:{agent} | {auth} | shell"


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


def render_signin(state: SessionState) -> str:
    link = SignInLink(url=signin_url())
    lines = [
        TITLE,
        "signed out",
        "",
        "Sign in with the official console (API key). No cookies are scraped.",
        *link.display_lines(),
        "",
        "Press Enter to open the browser, then paste the key, or /login",
        "Loopback callback (optional): start /login then open",
        "http://127.0.0.1:<port>/callback?api_key=…",
        "",
        TITLE,
    ]
    if state.auth_error:
        lines.insert(2, f"error: {state.auth_error}  (retry /login)")
    return "\n".join(lines)


def render_agent_list(state: SessionState, *, terminal_width: int | None = None) -> str:
    width = terminal_width or shutil.get_terminal_size((80, 24)).columns
    lines = [TITLE, "Agents / models", ""]
    if not state.agents:
        lines.append("No agents returned. /agents to refresh.")
        lines.append(render_footer(state))
        return "\n".join(lines)
    for i, agent in enumerate(state.agents):
        mark = ">" if i == state.agent_index else " "
        sprite = sprite_column(agent.seed, terminal_width=width)
        ident = agent.id if len(agent.id) <= 28 else agent.id[:25] + "…"
        blurb = agent.blurb if len(agent.blurb) <= 40 else agent.blurb[:37] + "…"
        glyph = sprite[0] if sprite else ""
        lines.append(f"{mark} {glyph}  {agent.name}")
        for extra in sprite[1:]:
            lines.append(f"    {extra}")
        lines.append(f"    {blurb}  {ident}")
    lines.append("")
    lines.append(render_footer(state))
    return "\n".join(lines)


def render_screen(state: SessionState) -> str:
    if state.auth_state != "signed_in":
        return render_signin(state)
    if state.view == "agents":
        return render_agent_list(state)
    return f"{render_header(state)}\n{render_transcript(state)}\n{render_footer(state)}"


def handle_command(line: str, state: SessionState) -> CommandResult:
    text = line.strip()
    if not text:
        if state.auth_state != "signed_in":
            return CommandResult("login")
        return CommandResult("empty")

    if not text.startswith("/"):
        if state.auth_state != "signed_in" or not state.has_api:
            if len(text) >= 8:
                return CommandResult("login", text)
            return CommandResult("login")
        if state.view == "agents":
            if text in ("j", "n"):
                return CommandResult("agent_down")
            if text in ("k", "p"):
                return CommandResult("agent_up")
            return CommandResult("agent_select")
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
    if name == "/login":
        return CommandResult("login", arg)
    if name == "/logout":
        return CommandResult("logout")
    if name == "/whoami":
        return CommandResult("whoami")
    if name == "/agents":
        return CommandResult("agents")
    if name == "/model":
        if arg:
            state.model = arg
            return CommandResult("model", f"chat model set to {state.model}.")
        return CommandResult("model", f"chat model: {state.model}")
    if name == "/chat":
        if state.auth_state != "signed_in" or not state.has_api:
            return CommandResult("need_key", "signed out. /login or set XAI_API_KEY.")
        state.view = "chat"
        if arg:
            return CommandResult("chat", send_text=arg)
        return CommandResult("chat", "Type a message to send.")
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def _toolbar(state: SessionState) -> str:
    return render_footer(state)


def _apply_key(state: SessionState, store: CredentialStore, key: str, cfg: Config) -> tuple[GrokClient, AgentCatalog]:
    store.save(key)
    state.has_api = True
    state.auth_state = "signed_in"
    state.auth_label = mask_secret(key)
    state.auth_error = ""
    state.view = "agents"
    client = GrokClient(api_key=key, model=cfg.model, timeout=cfg.timeout, base_url=cfg.base_url)
    catalog = AgentCatalog(key, base_url=cfg.base_url, timeout=min(cfg.timeout, 30.0))
    return client, catalog


def _do_login(
    state: SessionState,
    store: CredentialStore,
    cfg: Config,
    *,
    pasted: str = "",
    open_fn: Callable[[str], bool] | None = None,
) -> tuple[GrokClient | None, AgentCatalog | None, str]:
    if pasted:
        try:
            client, catalog = _apply_key(state, store, pasted, cfg)
        except ValueError:
            state.auth_state = "error"
            state.auth_error = "empty key"
            return None, None, "error: empty key  (retry /login)"
        return client, catalog, f"signed in as {state.auth_label}"

    url = signin_url()
    link = SignInLink(url=url)
    catcher = LoopbackCatcher()
    callback = catcher.start()
    state.auth_state = "waiting"
    print("Complete sign-in in browser…")
    for line in link.display_lines():
        print(line)
    print(f"Loopback (needs a free 127.0.0.1 port): {callback}?api_key=YOUR_KEY")
    print("Paste the API key here, or finish in the browser callback.")
    opened = open_browser(url, opener=open_fn)
    if not opened:
        print("(could not open a browser; copy the URL above)")
    try:
        got = catcher.wait(timeout=1.0)
        key = (got.get("api_key") or got.get("key") or got.get("code") or "").strip()
        if key:
            client, catalog = _apply_key(state, store, key, cfg)
            return client, catalog, f"signed in as {state.auth_label}"
    finally:
        catcher.stop()
    state.auth_state = "signed_out"
    return None, None, "waiting for key — paste it, or /login <key>"


def run_shell(
    cfg: Config,
    client: GrokClient | None,
    *,
    gui_popen: Callable[..., object] | None = None,
    gui_candidates: list[Path] | None = None,
    gui_arch: str | None = None,
    store: CredentialStore | None = None,
    catalog: AgentCatalog | None = None,
) -> int:
    creds = store or CredentialStore()
    loaded = creds.load()
    has_api = cfg.has_api_key or bool(loaded.get("api_key"))
    key = cfg.api_key or str(loaded.get("api_key") or "") or None
    state = SessionState(
        system=cfg.system,
        model=cfg.model,
        has_api=bool(has_api and key),
        auth_label=str(loaded.get("label") or mask_secret(key)),
    )
    if key and client is None:
        client = GrokClient(api_key=key, model=cfg.model, timeout=cfg.timeout, base_url=cfg.base_url)
    if key and catalog is None:
        catalog = AgentCatalog(key, base_url=cfg.base_url, timeout=min(cfg.timeout, 30.0))
    if state.has_api and catalog is not None:
        try:
            catalog.refresh()
            state.agents = list(catalog.cache)
            if state.agents:
                state.model = state.agents[0].id
                state.bot_name = state.agents[0].name
        except GrokAPIError as exc:
            state.auth_error = str(exc)

    session: PromptSession[str] = PromptSession(bottom_toolbar=lambda: _toolbar(state))
    print(render_screen(state))
    print(f"{TITLE} {__version__}. Companion shell — this is not Grok.")
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
            if result.kind == "login":
                pasted = result.message if result.message.startswith("xai-") or len(result.message) > 12 else ""
                if result.message and not pasted and result.message not in ("",):
                    # /login <key>
                    pasted = result.message
                new_client, new_catalog, msg = _do_login(state, creds, cfg, pasted=pasted)
                if new_client is not None:
                    if client is not None:
                        client.close()
                    client = new_client
                if new_catalog is not None:
                    if catalog is not None:
                        catalog.close()
                    catalog = new_catalog
                    try:
                        catalog.refresh()
                        state.agents = list(catalog.cache)
                    except GrokAPIError as exc:
                        state.auth_error = str(exc)
                        print(f"error: {exc}  (retry /login)")
                print(msg)
                print(render_screen(state))
                continue
            if result.kind == "logout":
                creds.clear()
                state.has_api = False
                state.auth_state = "signed_out"
                state.auth_label = ""
                state.agents = []
                state.view = "sign_in"
                if client is not None:
                    client.close()
                    client = None
                if catalog is not None:
                    catalog.close()
                    catalog = None
                print("signed out")
                print(render_screen(state))
                continue
            if result.kind == "whoami":
                if state.auth_state != "signed_in":
                    print("signed out")
                else:
                    print(f"signed in  {state.auth_label or mask_secret(None)}")
                continue
            if result.kind == "agents":
                if catalog is None:
                    print("signed out. /login first.")
                    continue
                try:
                    catalog.refresh()
                    state.agents = list(catalog.cache)
                    state.view = "agents"
                    print(render_agent_list(state))
                except GrokAPIError as exc:
                    print(f"error: {exc}  (retry /agents)")
                continue
            if result.kind == "agent_down":
                if state.agents:
                    state.agent_index = (state.agent_index + 1) % len(state.agents)
                print(render_agent_list(state))
                continue
            if result.kind == "agent_up":
                if state.agents:
                    state.agent_index = (state.agent_index - 1) % len(state.agents)
                print(render_agent_list(state))
                continue
            if result.kind == "agent_select":
                agent = state.active_agent
                if agent:
                    state.model = agent.id
                    state.bot_name = agent.name
                    state.view = "chat"
                    if client is not None:
                        client.model = agent.id
                    print(f"active agent: {agent.name}")
                    print(render_screen(state))
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
        print("signed out. /login or set XAI_API_KEY.")
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
    store = CredentialStore()
    loaded = store.load()
    key = cfg.api_key or str(loaded.get("api_key") or "") or None
    client: GrokClient | None = None
    catalog: AgentCatalog | None = None
    if key:
        client = GrokClient(
            api_key=key,
            model=cfg.model,
            timeout=cfg.timeout,
            base_url=cfg.base_url,
        )
        catalog = AgentCatalog(key, base_url=cfg.base_url, timeout=min(cfg.timeout, 30.0))
    try:
        return run_shell(cfg, client, store=store, catalog=catalog)
    except KeyboardInterrupt:
        print()
        return 0
    finally:
        if client is not None:
            client.close()
        if catalog is not None:
            catalog.close()
