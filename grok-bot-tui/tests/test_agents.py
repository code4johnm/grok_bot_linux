"""Offline: model list normalize + mocked GET /models."""

from __future__ import annotations

import httpx

from grok_bot_tui.agents import AgentCatalog, normalize_list
from grok_bot_tui.app import SessionState, handle_command, render_agent_list, render_signin
from grok_bot_tui.auth import DEFAULT_AUTHORIZE_URL
from grok_bot_tui.grok_bot_session import BOT_HOME_URL, BOT_ONBOARDING_URL


def test_normalize_openai_style_models() -> None:
    payload = {
        "data": [
            {"id": "grok-4.6", "object": "model", "owned_by": "xai"},
            {"id": "grok-4.5", "name": "Grok 4.5"},
        ]
    }
    agents = normalize_list(payload)
    ids = [a.id for a in agents]
    assert "grok-4.6" in ids
    assert "grok-4.5" in ids


def test_catalog_refresh_mocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        assert "Bearer" in request.headers.get("Authorization", "")
        return httpx.Response(
            200,
            json={"data": [{"id": "grok-4.6", "owned_by": "xai"}]},
        )

    catalog = AgentCatalog(
        "test-key",
        transport=httpx.MockTransport(handler),
    )
    rows = catalog.refresh()
    catalog.close()
    assert rows[0].id == "grok-4.6"


def test_signed_out_screen_has_osc8_and_raw_url() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    text = render_signin(state)
    assert "Grok GUI TUI shell" in text
    assert "signed out" in text
    assert DEFAULT_AUTHORIZE_URL == BOT_ONBOARDING_URL
    assert BOT_ONBOARDING_URL in text
    assert BOT_HOME_URL in text
    assert "accounts.x.ai" not in text
    assert "\033]8;;" in text
    assert "Sign in with browser" in text


def test_empty_agents_and_nav() -> None:
    state = SessionState(system="sys", model="grok-4.6", has_api=True)
    state.auth_state = "signed_in"
    state.view = "agents"
    empty = render_agent_list(state, terminal_width=80)
    assert "No bots in the Grok Bot cache" in empty
    from grok_bot_tui.agents import Agent

    state.agents = [
        Agent(id="grok-4.6", name="Grok 4.6", blurb="flagship"),
        Agent(id="grok-4.5", name="Grok 4.5", blurb="prior"),
    ]
    assert handle_command("j", state).kind == "agent_down"
    assert handle_command("k", state).kind == "agent_up"
    typed = handle_command("hello there", state)
    assert typed.kind == "agent_select"
    assert typed.send_text == "hello there"
    assert handle_command("/agents", state).kind == "agents"
    assert handle_command("/whoami", state).kind == "whoami"
    assert handle_command("/logout", state).kind == "logout"
    assert handle_command("/login", state).kind == "login"
    listed = render_agent_list(state, terminal_width=80)
    assert "2 from signed-in Grok Bot" in listed
    assert "▀" in listed
    assert "\033[" in listed
    assert any("Grok 4.6" in ln and "flagship" in ln for ln in listed.splitlines())
    data_rows = [ln for ln in listed.splitlines() if "flagship" in ln or "prior" in ln]
    assert len(data_rows) == 2
