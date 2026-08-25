"""Offline: Grok Bot GUI session heuristic and roster. No cookie parse. No live SSO."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest

from grok_bot_tui.app import SessionState, _do_sso_login, render_agent_list
from grok_bot_tui.grok_bot_session import (
    BOT_ONBOARDING_URL,
    last_selected_agent_id,
    persistence_blob_name,
    session_bots,
    session_looks_signed_in,
    set_ignore_gui_session,
    wait_for_gui_session,
)


def _write_settings(folder: Path, body: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "settings.json"
    path.write_text(body, encoding="utf-8")
    return path


def _write_slice(cfg: Path, key: str, value: object, *, schema: int = 1) -> Path:
    folder = cfg / "sand-client-persistence"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / persistence_blob_name(key)
    path.write_text(
        json.dumps({"schemaVersion": schema, "value": value}) + "\n",
        encoding="utf-8",
    )
    return path


def _write_roster(
    cfg: Path,
    rows: list[dict[object, object]],
    *,
    slot: str = "grok|user_test",
    selected: str | None = None,
    pinned: list[str] | None = None,
) -> None:
    _write_slice(cfg, "sand.client.slice.client-meta.account-slot", slot)
    prefix = f"sand.client.slice.account.{quote(slot, safe='')}."
    _write_slice(cfg, prefix + "roster.last-roster", {"rows": rows}, schema=2)
    if selected:
        _write_slice(cfg, prefix + "selection.last-agent", {"agentId": selected})
    if pinned is not None:
        _write_slice(
            cfg,
            prefix + "ui-agent-refs",
            {"pinnedAgentIds": pinned, "collapsedSectionIds": [], "mentionRecents": [], "emojiRecents": []},
        )


def test_unsigned_empty_dirs(tmp_path: Path) -> None:
    assert session_looks_signed_in(cfg=tmp_path / "cfg", data=tmp_path / "data") is False


def test_onboarding_account_scope_means_signed_in(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _write_settings(
        data,
        '{"hasSeenOnboardingAccountScope":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","accountScopes":{}}',
    )
    cookies = tmp_path / "cfg" / "Cookies"
    cookies.parent.mkdir(parents=True, exist_ok=True)
    cookies.write_text("must-not-be-read-as-a-session-token", encoding="utf-8")
    assert session_looks_signed_in(cfg=tmp_path / "cfg", data=data) is True


def test_empty_account_scopes_without_hash_is_unsigned(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _write_settings(data, '{"hasSeenOnboarding":true,"accountScopes":{}}')
    assert session_looks_signed_in(cfg=tmp_path / "cfg", data=data) is False


def test_nonempty_account_scopes_means_signed_in(tmp_path: Path) -> None:
    data = tmp_path / "data"
    _write_settings(data, '{"accountScopes":{"cursor":{"ok":true}}}')
    assert session_looks_signed_in(cfg=tmp_path / "cfg", data=data) is True


def test_does_not_open_cookies_file(tmp_path: Path) -> None:
    cfg = tmp_path / "cfg"
    cookies = cfg / "Cookies"
    cookies.parent.mkdir(parents=True, exist_ok=True)
    cookies.write_text("secret-cookie-value", encoding="utf-8")
    assert session_looks_signed_in(cfg=cfg, data=tmp_path / "data") is False
    assert cookies.read_text(encoding="utf-8") == "secret-cookie-value"


def test_wait_for_gui_session_polls() -> None:
    hits = {"n": 0}

    def check() -> bool:
        hits["n"] += 1
        return hits["n"] >= 3

    slept: list[float] = []
    assert wait_for_gui_session(timeout=5, interval=1, check=check, sleep=slept.append) is True
    assert slept == [1, 1]
    assert hits["n"] >= 3


def test_wait_timeout_zero_does_not_sleep() -> None:
    slept: list[float] = []
    assert wait_for_gui_session(timeout=0, check=lambda: False, sleep=slept.append) is False
    assert slept == []


def test_session_bots_from_roster_not_starters(tmp_path: Path) -> None:
    cfg = tmp_path / "Grok Bot"
    cookies = cfg / "Cookies"
    cookies.parent.mkdir(parents=True, exist_ok=True)
    cookies.write_text("must-not-appear", encoding="utf-8")
    secrets = cfg / "sand-secrets.json"
    secrets.write_text('{"token":"must-not-appear"}', encoding="utf-8")
    _write_roster(
        cfg,
        [
            {
                "id": "bot-night",
                "name": "Night Watch",
                "description": "overnight checks\nsecond line",
                "unreadCount": 2,
                "isHiddenFromSidebar": False,
                "lastEntry": {"text": "must-not-appear", "api_key": "secret-key"},
            },
            {
                "id": "bot-hidden",
                "name": "Hidden Bot",
                "description": "stay off the list",
                "isHiddenFromSidebar": True,
            },
            {
                "id": "bot-ops",
                "name": "Ops",
                "description": "queue",
                "unreadCount": 0,
            },
        ],
        selected="bot-ops",
        pinned=["bot-ops"],
    )
    rows = session_bots(cfg=cfg)
    names = [row["name"] for row in rows]
    assert names == ["Ops", "Night Watch"]
    assert "Hidden Bot" not in names
    assert "Sales Outbound" not in names
    blob = json.dumps(rows)
    assert "must-not-appear" not in blob
    assert "secret-key" not in blob
    night = next(row for row in rows if row["name"] == "Night Watch")
    assert "2 unread" in night["blurb"]
    assert "overnight checks" in night["blurb"]
    assert last_selected_agent_id(cfg=cfg) == "bot-ops"


def test_login_uses_session_roster(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GROK_BOT_TUI_HOME", str(tmp_path / "tui"))
    monkeypatch.setenv("GROK_BOT_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    set_ignore_gui_session(False)
    cfg = tmp_path / "xdg" / "Grok Bot"
    _write_roster(
        cfg,
        [
            {"id": "bot-night", "name": "Night Watch", "description": "overnight checks"},
            {"id": "bot-ops", "name": "Ops", "description": "queue"},
        ],
        selected="bot-night",
    )
    spawned: list[list[str]] = []
    desktop = tmp_path / "grok-bot"
    desktop.write_text("#!/bin/sh\n", encoding="utf-8")
    desktop.chmod(0o755)

    def fake_popen(cmd: list[str], **_kwargs: object) -> object:
        spawned.append(cmd)
        return object()

    opened: list[str] = []
    state = SessionState(system="sys", model="grok-4.6", has_api=False)
    msg = _do_sso_login(
        state,
        open_fn=lambda url: opened.append(url) or True,
        gui_popen=fake_popen,
        gui_candidates=[desktop],
        gui_arch="x86_64",
        signed_in=lambda: True,
        sleep=lambda _s: None,
        timeout=2,
    )
    out = capsys.readouterr().out
    assert BOT_ONBOARDING_URL in out
    assert "\033]8;;" in out
    assert "accounts.x.ai" not in out
    assert "grok login" not in out.lower()
    assert spawned == [[str(desktop)]]
    assert opened == [BOT_ONBOARDING_URL]
    assert "signed in" in msg
    assert state.auth_state == "signed_in"
    names = [a.name for a in state.agents]
    assert names == ["Night Watch", "Ops"]
    assert "Sales Outbound" not in names
    assert state.active_agent is not None
    assert state.active_agent.name == "Night Watch"
    listed = render_agent_list(state, terminal_width=80)
    assert "Night Watch" in listed
    assert "Ops" in listed
    assert "Sales Outbound" not in listed
    assert any(ch in listed for ch in "▀▄█░")
    assert "bot:" in listed
