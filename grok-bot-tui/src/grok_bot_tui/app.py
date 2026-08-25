"""Grok GUI TUI shell: Grok Bot sign-in, bot picker, one chat thread."""

from __future__ import annotations

import os
import shutil
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.output.color_depth import ColorDepth
from prompt_toolkit.styles import Style

from grok_bot_tui import TITLE, __version__
from grok_bot_tui.agents import Agent, AgentCatalog
from grok_bot_tui.auth import (
    CredentialStore,
    SignInLink,
    mask_secret,
    open_browser,
    signin_url,
)
from grok_bot_tui.client import GrokAPIError, GrokClient
from grok_bot_tui.grok_bot_auth import load_access_token
from grok_bot_tui.grok_bot_client import GrokBotAPIError, GrokBotClient, transcript_messages
from grok_bot_tui.config import Config, load_config
from grok_bot_tui.grok_bot_session import (
    BOT_HOME_URL,
    last_selected_agent_id,
    load_identity,
    session_bots,
    set_ignore_gui_session,
    wait_for_gui_session,
)
from grok_bot_tui.gui import launch_grok_bot
from grok_bot_tui.pixel import sprite_inline

NEED_BOT_MSG = (
    "Could not read Grok Bot credentials. Chat uses the same session as grok-bot."
)

HELP = f"""{TITLE}
Companion TUI for Grok Bot. Chat stays in this terminal. This is not Grok.

  /login          Sign in with grok-bot — this TUI uses that same session
  /logout         Sign this TUI out
  /whoami         Show Grok Bot session label
  /agents         Refresh bots from the signed-in Grok Bot roster
  j / k  or ↑↓    Move selection (bot list)
  Enter           Chat with the selected bot in this TUI
  <text>          Send a message to that Grok Bot in this terminal
  /gui            Optional desktop (never used for chat)
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
    notice: str = ""
    streaming: bool = False

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
    bot = state.active_agent.name if state.active_agent else state.bot_name or "-"
    if state.streaming:
        phase = "streaming"
    elif state.auth_state == "signed_in":
        phase = "signed in"
    else:
        phase = state.auth_state.replace("_", " ")
    return f"bot:{bot} | {phase} | shell"


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
        "Companion for Grok Bot (the Electron GUI). This is not Grok.",
        *link.display_lines(),
        BOT_HOME_URL,
        "",
        "Enter or /login launches grok-bot for Cursor SSO.",
        "j/k or arrows move the bot list after sign-in. /help for commands.",
    ]
    if state.auth_error:
        lines.insert(2, f"error: {state.auth_error}  (retry /login)")
    return "\n".join(lines)


def render_agent_list(state: SessionState, *, terminal_width: int | None = None) -> str:
    width = terminal_width or shutil.get_terminal_size((80, 24)).columns
    lines = [TITLE, f"Bots  ({len(state.agents)} from signed-in Grok Bot)", ""]
    if not state.agents:
        lines.append("No bots in the Grok Bot cache yet. Open grok-bot, then /agents.")
        lines.append("")
        lines.append(render_footer(state))
        return "\n".join(lines)
    name_w = 22
    for i, agent in enumerate(state.agents):
        mark = ">" if i == state.agent_index else " "
        glyph = sprite_inline(agent.seed, terminal_width=width, truecolor=True)
        name = agent.name if len(agent.name) <= name_w else agent.name[: name_w - 1] + "…"
        blurb = agent.blurb if len(agent.blurb) <= 36 else agent.blurb[:33] + "…"
        lines.append(f"{mark} {glyph}  {name:<{name_w}} {blurb}")
    lines.append("")
    lines.append("↑↓ / j k  select   Enter  chat in this terminal")
    lines.append(render_footer(state))
    return "\n".join(lines)


def render_screen(state: SessionState) -> str:
    if state.auth_state != "signed_in":
        return render_signin(state)
    if state.view == "agents":
        return render_agent_list(state)
    return f"{render_header(state)}\n{render_transcript(state)}\n{render_footer(state)}"


def render_body(state: SessionState, *, terminal_width: int | None = None) -> str:
    """Main pane without repeating the header/footer chrome."""
    if state.auth_state != "signed_in":
        lines = render_signin(state).splitlines()
        return "\n".join(lines[1:] if lines[:1] == [TITLE] else lines)
    if state.view == "agents":
        lines = render_agent_list(state, terminal_width=terminal_width).splitlines()
        if lines[:1] == [TITLE]:
            lines = lines[1:]
        if lines and lines[-1] == render_footer(state):
            lines = lines[:-1]
        return "\n".join(lines).rstrip()
    return render_transcript(state)


def handle_command(line: str, state: SessionState) -> CommandResult:
    text = line.strip()
    if not text:
        if state.auth_state != "signed_in":
            return CommandResult("login")
        return CommandResult("empty")

    if not text.startswith("/"):
        if state.auth_state != "signed_in":
            if text.lower().startswith("xai-") or (len(text) > 24 and " " not in text):
                return CommandResult("login_key", text)
            return CommandResult("login")
        if state.view == "agents":
            if text in ("j", "n"):
                return CommandResult("agent_down")
            if text in ("k", "p"):
                return CommandResult("agent_up")
            # Typing on the list is a message to the highlighted bot, not a silent select.
            return CommandResult("agent_select", send_text=text)
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
    if name == "/login-key":
        return CommandResult("login_key", arg)
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
        if state.auth_state != "signed_in":
            return CommandResult("login")
        state.view = "chat"
        if arg:
            return CommandResult("chat", send_text=arg)
        return CommandResult("chat", "Type a message to send.")
    return CommandResult("unknown", f"Unknown command {cmd}. Try /help.")


def bot_system_prompt(agent: Agent | None, fallback: str) -> str:
    if agent is None:
        return fallback
    body = (agent.instructions or agent.blurb or "").strip()
    head = (
        f"You are {agent.name}, a teammate in Grok GUI TUI shell. "
        "Reply in this terminal only. This is not Grok."
    )
    return f"{head}\n{body}".strip() if body else head


def _enter_bot_chat(state: SessionState, agent: Agent) -> None:
    state.bot_name = agent.name
    state.view = "chat"
    state.system = bot_system_prompt(agent, state.system)
    state.reset_messages()


def _load_history(state: SessionState, client: GrokBotClient, agent: Agent) -> None:
    """Fill the chat view from this bot's Grok Bot transcript (newest API rows reversed)."""
    try:
        listed = client.list_transcript(agent.id, limit=80)
    except GrokBotAPIError:
        return
    rows = transcript_messages(listed.get("entries"), agent.id)
    if not rows:
        return
    state.reset_messages()
    state.messages.extend(rows)


def _fill_session_bots(state: SessionState) -> None:
    rows = session_bots()
    state.agents = [
        Agent(
            id=r["id"],
            name=r["name"],
            blurb=r["blurb"],
            instructions=r.get("instructions") or "",
        )
        for r in rows
    ]
    state.agent_index = 0
    selected = last_selected_agent_id()
    if selected:
        for i, agent in enumerate(state.agents):
            if agent.id == selected:
                state.agent_index = i
                break
    if state.agents:
        state.bot_name = state.agents[state.agent_index].name


def _apply_gui_session(state: SessionState, *, assumed: bool = False) -> str:
    ident = load_identity()
    if not ident.signed_in and not assumed:
        state.auth_state = "error"
        state.auth_error = "Grok Bot GUI sign-in did not complete"
        return "error: Grok Bot GUI sign-in did not complete  (retry /login)"
    state.auth_state = "signed_in"
    state.auth_label = ident.label or "Grok Bot GUI session"
    state.auth_error = ""
    state.view = "agents"
    _fill_session_bots(state)
    return f"signed in as {state.auth_label}"


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


def _do_sso_login(
    state: SessionState,
    *,
    open_fn: Callable[[str], bool] | None = None,
    gui_popen: Callable[..., object] | None = None,
    gui_candidates: list[Path] | None = None,
    gui_arch: str | None = None,
    signed_in: Callable[[], bool] | None = None,
    sleep: Callable[[float], None] | None = None,
    timeout: float = 20.0,
    emit: Callable[[str], None] | None = None,
) -> str:
    log = emit or print
    set_ignore_gui_session(False)
    ident = load_identity()
    if ident.signed_in:
        return _apply_gui_session(state)

    url = signin_url()
    link = SignInLink(url=url)
    log("Complete sign-in in Grok Bot (same window as the GUI).")
    log("Cookies are not scraped.")
    for row in link.display_lines():
        log(row)
    log(BOT_HOME_URL)
    open_browser(url, opener=open_fn)
    log(
        launch_grok_bot(
            popen=gui_popen,
            candidates=gui_candidates,
            arch=gui_arch,
        )
    )
    state.auth_state = "waiting"
    if wait_for_gui_session(timeout=timeout, check=signed_in, sleep=sleep):
        return _apply_gui_session(state, assumed=True)
    state.auth_error = "waiting for Grok Bot GUI sign-in"
    return "waiting for Grok Bot GUI sign-in  (retry /login after you finish SSO)"


def _do_login_key(
    state: SessionState,
    store: CredentialStore,
    cfg: Config,
    pasted: str,
) -> tuple[GrokClient | None, AgentCatalog | None, str]:
    if not pasted:
        url = signin_url(keys=True)
        link = SignInLink(url=url, label="Open API keys console")
        print("API-key fallback only. Prefer /login for Grok Bot GUI SSO.")
        for row in link.display_lines():
            print(row)
        return None, None, "paste the key, or /login-key <key>"
    try:
        client, catalog = _apply_key(state, store, pasted, cfg)
    except ValueError:
        state.auth_state = "error"
        state.auth_error = "empty key"
        return None, None, "error: empty key  (retry /login-key)"
    if not state.agents:
        _fill_session_bots(state)
    return client, catalog, f"signed in as {state.auth_label}"


def _init_state(
    cfg: Config,
    client: GrokClient | None,
    catalog: AgentCatalog | None,
    creds: CredentialStore,
) -> tuple[SessionState, GrokClient | None, AgentCatalog | None]:
    loaded = creds.load()
    ident = load_identity()
    token = load_access_token()
    signed = ident.signed_in
    state = SessionState(
        system=cfg.system,
        model=cfg.model,
        has_api=signed,
        auth_label=(ident.label if ident.signed_in else ""),
    )
    if ident.signed_in:
        state.auth_state = "signed_in"
        state.view = "agents"
        _fill_session_bots(state)
    if token and not isinstance(client, GrokBotClient):
        if client is not None and hasattr(client, "close"):
            client.close()
        client = GrokBotClient(token, timeout=min(cfg.timeout, 120.0))
    if ident.signed_in and not state.agents:
        _fill_session_bots(state)
    elif signed and not state.agents:
        _fill_session_bots(state)
    return state, client, catalog


def run_shell(
    cfg: Config,
    client: GrokBotClient | GrokClient | None,
    *,
    gui_popen: Callable[..., object] | None = None,
    gui_candidates: list[Path] | None = None,
    gui_arch: str | None = None,
    store: CredentialStore | None = None,
    catalog: AgentCatalog | None = None,
    login_signed_in: Callable[[], bool] | None = None,
    login_sleep: Callable[[float], None] | None = None,
    login_timeout: float = 20.0,
) -> int:
    creds = store or CredentialStore()
    state, client, catalog = _init_state(cfg, client, catalog, creds)

    holder: dict[str, object] = {"client": client, "catalog": catalog, "app": None}

    def emit(msg: str) -> None:
        state.notice = msg
        app = holder.get("app")
        if app is not None:
            app.invalidate()  # type: ignore[union-attr]

    def apply_line(line: str) -> bool:
        """Dispatch one compose line. Return False to quit."""
        nonlocal client, catalog
        result = handle_command(line, state)
        if result.kind == "quit":
            return False
        if result.kind == "empty":
            if state.auth_state == "signed_in" and state.view == "agents":
                result = CommandResult("agent_select")
            else:
                return True
        if result.kind == "login":
            emit("Launching grok-bot for Cursor SSO…")
            msg = _do_sso_login(
                state,
                gui_popen=gui_popen,
                gui_candidates=gui_candidates,
                gui_arch=gui_arch,
                signed_in=login_signed_in,
                sleep=login_sleep,
                timeout=login_timeout,
                emit=emit,
            )
            emit(msg)
            if not isinstance(client, GrokBotClient):
                token = load_access_token()
                if token:
                    if client is not None:
                        client.close()
                    client = GrokBotClient(token, timeout=min(cfg.timeout, 120.0))
                    holder["client"] = client
            return True
        if result.kind == "login_key":
            new_client, new_catalog, msg = _do_login_key(state, creds, cfg, result.message)
            if new_client is not None and not isinstance(client, GrokBotClient):
                if client is not None:
                    client.close()
                client = new_client
                holder["client"] = client
            if new_catalog is not None:
                if catalog is not None:
                    catalog.close()
                catalog = new_catalog
                holder["catalog"] = catalog
                _fill_session_bots(state)
                if not state.agents:
                    try:
                        catalog.refresh()
                        api_agents = list(catalog.cache)
                        if api_agents:
                            state.agents = api_agents
                    except GrokAPIError as exc:
                        state.auth_error = str(exc)
                        emit(f"error: {exc}  (retry /login-key)")
            emit(msg)
            return True
        if result.kind == "logout":
            set_ignore_gui_session(True)
            creds.clear()
            state.has_api = False
            state.auth_state = "signed_out"
            state.auth_label = ""
            state.agents = []
            state.view = "sign_in"
            if client is not None:
                client.close()
                client = None
                holder["client"] = None
            if catalog is not None:
                catalog.close()
                catalog = None
                holder["catalog"] = None
            emit("signed out of this TUI. Sign out of Grok Bot in the desktop app to end that session.")
            return True
        if result.kind == "whoami":
            ident = load_identity()
            if ident.signed_in:
                emit(f"signed in  {ident.label}")
            elif state.auth_state == "signed_in":
                emit(f"signed in  {state.auth_label or mask_secret(None)}")
            else:
                emit("signed out")
            return True
        if result.kind == "agents":
            if state.auth_state != "signed_in":
                emit("signed out. /login first.")
                return True
            _fill_session_bots(state)
            state.view = "agents"
            if not state.agents:
                emit("No bots in the Grok Bot cache yet. Open grok-bot, then /agents.")
            else:
                emit("")
            return True
        if result.kind == "agent_down":
            if state.agents:
                state.agent_index = (state.agent_index + 1) % len(state.agents)
            emit("")
            return True
        if result.kind == "agent_up":
            if state.agents:
                state.agent_index = (state.agent_index - 1) % len(state.agents)
            emit("")
            return True
        if result.kind == "agent_select":
            agent = state.active_agent
            if agent:
                _enter_bot_chat(state, agent)
                if isinstance(client, GrokBotClient):
                    _load_history(state, client, agent)
                emit(f"active bot: {agent.name} — chatting in this terminal")
            if not result.send_text:
                return True
        if result.kind == "gui":
            emit(
                launch_grok_bot(
                    popen=gui_popen,
                    candidates=gui_candidates,
                    arch=gui_arch,
                )
            )
            return True
        if result.kind == "help":
            emit(result.message)
            return True
        if result.message:
            emit(result.message)
        if result.send_text:
            if state.streaming:
                emit("still responding…")
                return True
            if not isinstance(client, GrokBotClient):
                token = load_access_token()
                if token:
                    if client is not None:
                        client.close()
                    client = GrokBotClient(token, timeout=min(cfg.timeout, 120.0))
                    holder["client"] = client

            def refresh() -> None:
                app = holder.get("app")
                if app is None:
                    return
                try:
                    app.invalidate()  # type: ignore[union-attr]
                    renderer = getattr(app, "renderer", None)
                    layout = getattr(app, "layout", None)
                    if renderer is not None and layout is not None:
                        renderer.render(app, layout)
                except Exception:
                    pass

            def work() -> None:
                _send_chat(
                    state,
                    client,
                    result.send_text,
                    emit=emit,
                    refresh=refresh,
                )

            threading.Thread(target=work, daemon=True).start()
        return True

    compose = Buffer()
    kb = KeyBindings()
    list_nav = Condition(
        lambda: state.auth_state == "signed_in"
        and state.view == "agents"
        and not compose.text
    )

    @kb.add("c-c")
    @kb.add("c-d")
    @kb.add("c-q")
    def _quit(event: object) -> None:
        event.app.exit(result=0)  # type: ignore[attr-defined]

    @kb.add("enter")
    def _enter(event: object) -> None:
        text = compose.text
        compose.reset()
        if not apply_line(text):
            event.app.exit(result=0)  # type: ignore[attr-defined]
        else:
            event.app.invalidate()  # type: ignore[attr-defined]

    @kb.add("up", filter=list_nav)
    @kb.add("k", filter=list_nav)
    def _up(event: object) -> None:
        apply_line("k")
        event.app.invalidate()  # type: ignore[attr-defined]

    @kb.add("down", filter=list_nav)
    @kb.add("j", filter=list_nav)
    def _down(event: object) -> None:
        apply_line("j")
        event.app.invalidate()  # type: ignore[attr-defined]

    def header_text() -> ANSI:
        return ANSI(f"{TITLE}  {__version__}")

    def body_text() -> ANSI:
        width = shutil.get_terminal_size((80, 24)).columns
        chunks: list[str] = []
        if state.notice:
            chunks.append(state.notice.rstrip())
            chunks.append("")
        chunks.append(render_body(state, terminal_width=width))
        return ANSI("\n".join(chunks))

    def footer_text() -> str:
        return render_footer(state)

    layout = Layout(
        HSplit(
            [
                Window(FormattedTextControl(header_text), height=1, style="class:header"),
                Window(FormattedTextControl(body_text), wrap_lines=True),
                Window(height=1, char="─", style="class:rule"),
                Window(
                    BufferControl(
                        buffer=compose,
                        input_processors=[BeforeInput("compose> ", style="class:prompt")],
                    ),
                    height=1,
                    style="class:compose",
                ),
                Window(FormattedTextControl(footer_text), height=1, style="class:footer"),
            ]
        )
    )
    style = Style.from_dict(
        {
            "header": "bold reverse",
            "footer": "reverse",
            "rule": "ansibrightblack",
            "prompt": "bold ansicyan",
        }
    )
    if sys.stdin.isatty() and os.environ.get("GROK_TUI_NO_COLOR", "").strip() != "1":
        os.environ.pop("NO_COLOR", None)
        os.environ.setdefault("COLORTERM", "truecolor")
    app: Application[int] = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
        style=style,
        color_depth=ColorDepth.TRUE_COLOR,
    )
    holder["app"] = app
    try:
        result = app.run()
    except (KeyboardInterrupt, EOFError):
        return 0
    return int(result or 0)


def _send_chat(
    state: SessionState,
    client: GrokBotClient | GrokClient | None,
    text: str,
    *,
    emit: Callable[[str], None] | None = None,
    refresh: Callable[[], None] | None = None,
) -> None:
    """Stream a Grok Bot reply into the TUI. Never launches a GUI. Never uses xAI API keys."""
    log = emit or print
    if not isinstance(client, GrokBotClient):
        token = load_access_token()
        if token:
            client = GrokBotClient(token, timeout=120.0)
        else:
            state.messages.append({"role": "user", "content": text})
            state.messages.append({"role": "assistant", "content": NEED_BOT_MSG})
            log(NEED_BOT_MSG)
            return
    if state.streaming:
        log("still responding…")
        return
    agent = state.active_agent
    if agent is None:
        state.messages.append({"role": "user", "content": text})
        state.messages.append({"role": "assistant", "content": "Select a bot first."})
        log("Select a bot first.")
        return
    state.messages.append({"role": "user", "content": text})
    draft: dict[str, str] = {"role": "assistant", "content": ""}
    state.messages.append(draft)
    payload = [item for item in state.messages if item is not draft]
    state.streaming = True
    log(f"Waiting for {agent.name}…")
    if refresh:
        refresh()
    try:
        parts: list[str] = []
        for token in client.stream_text(payload, agent_id=agent.id):
            parts.append(token)
            draft["content"] = "".join(parts)
            if refresh:
                refresh()
        if not draft["content"]:
            state.messages.pop()
        log("")
    except GrokBotAPIError as exc:
        draft["content"] = str(exc)
        log(str(exc))
    finally:
        state.streaming = False
        if refresh:
            refresh()


def main(argv: list[str] | None = None) -> int:
    cfg = load_config(argv)
    if cfg.command != "tui":
        from grok_bot_tui.cli import run_cli

        return run_cli(cfg)
    if not sys.stdin.isatty() and os.environ.get("GROK_TUI_ALLOW_NOTTY", "").strip() != "1":
        print(
            "error: no TTY. Use grok-tui-shell version|whoami|bots|status|chat, "
            "or run inside a terminal / tmux (Raspberry Pi autostart).",
            file=sys.stderr,
        )
        print("This is not Grok.", file=sys.stderr)
        return 2
    store = CredentialStore()
    token = load_access_token()
    client: GrokBotClient | None = None
    catalog: AgentCatalog | None = None
    if token:
        client = GrokBotClient(token, timeout=min(cfg.timeout, 120.0))
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
