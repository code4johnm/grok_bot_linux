"""Offline: grok CLI device-login parser and identity load. No live SSO."""

from __future__ import annotations

import json
from pathlib import Path

from grok_bot_tui.grok_session import (
    load_cached_models,
    load_identity,
    parse_device_login_output,
)


SAMPLE_DEVICE = """
To sign in, open this URL in your browser:

  https://accounts.x.ai/oauth2/device?user_code=ABCD-1234

Confirm this code in your browser:

  ABCD-1234

Waiting for authorization...
"""


def test_parse_device_login_output() -> None:
    prompt = parse_device_login_output(SAMPLE_DEVICE)
    assert prompt is not None
    assert prompt.user_code == "ABCD-1234"
    assert prompt.url.startswith("https://accounts.x.ai/oauth2/device?user_code=")
    assert "ABCD-1234" in prompt.url


def test_load_identity_fixture(tmp_path: Path) -> None:
    path = tmp_path / "auth.json"
    path.write_text(
        json.dumps(
            {
                "https://auth.x.ai::example": {
                    "auth_mode": "oidc",
                    "email": "user@example.org",
                    "first_name": "Operator",
                    "user_id": "usr_example",
                    "oidc_issuer": "https://auth.x.ai",
                    "key": "session-token-placeholder",
                    "refresh_token": "refresh-placeholder",
                }
            }
        ),
        encoding="utf-8",
    )
    ident = load_identity(path)
    assert ident is not None
    assert ident.signed_in
    assert ident.label.startswith("Operator")
    assert "user@example.org" not in ident.label
    assert "***@example.org" in ident.label
    assert "session-token-placeholder" not in ident.label


def test_cached_models_drop_secrets(tmp_path: Path) -> None:
    path = tmp_path / "models_cache.json"
    path.write_text(
        json.dumps(
            {
                "models": {
                    "grok-4.6": {
                        "api_key": "must-not-leak",
                        "info": {
                            "id": "grok-4.6",
                            "name": "Grok 4.6",
                            "description": "frontier",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    rows = load_cached_models(path)
    blob = json.dumps(rows)
    assert "must-not-leak" not in blob
    assert rows[0]["id"] == "grok-4.6"
    assert rows[0]["name"] == "Grok 4.6"
