"""Offline: Grok Bot secret-store token load. No Cookies. No live network."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from grok_bot_tui.grok_bot_auth import load_access_token, secrets_path


def test_plaintext_token_from_sand_secrets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GROK_BOT_ACCESS_TOKEN", raising=False)
    cfg = tmp_path / "Grok Bot"
    cfg.mkdir()
    token = "grok-bot-session-token-fixture"
    stored = "plaintext:v1:" + base64.b64encode(token.encode("utf-8")).decode("ascii")
    payload = {
        "cursor-accounts": json.dumps(
            {
                "active": "acct1",
                "accounts": {
                    "acct1": {
                        "cursor-access-token": stored,
                        "cursor-refresh-token": stored,
                    }
                },
            }
        )
    }
    path = cfg / "sand-secrets.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cookies = cfg / "Cookies"
    cookies.write_text("must-not-be-read", encoding="utf-8")
    monkeypatch.setattr("grok_bot_tui.grok_bot_auth.config_dir", lambda: cfg)
    assert secrets_path(cfg=cfg) == path
    assert load_access_token(cfg=cfg) == token
    assert cookies.read_text(encoding="utf-8") == "must-not-be-read"


def test_encrypted_blob_is_not_returned_as_token(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GROK_BOT_ACCESS_TOKEN", raising=False)
    cfg = tmp_path / "Grok Bot"
    cfg.mkdir()
    payload = {
        "cursor-accounts": json.dumps(
            {
                "active": "acct1",
                "accounts": {"acct1": {"cursor-access-token": "djExAAAA"}},
            }
        )
    }
    (cfg / "sand-secrets.json").write_text(json.dumps(payload), encoding="utf-8")
    assert load_access_token(cfg=cfg) is None


def test_env_token_wins(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GROK_BOT_ACCESS_TOKEN", "env-grok-bot-token")
    assert load_access_token(cfg=tmp_path) == "env-grok-bot-token"
