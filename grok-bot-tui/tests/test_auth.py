"""Offline: OSC 8 console link, authorize-URL hook, credential file 0600."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from grok_bot_tui.auth import (
    CONSOLE_KEYS_URL,
    CredentialStore,
    SignInLink,
    build_authorize_url,
    mask_secret,
    signin_url,
)


def test_signin_url_is_official_console() -> None:
    url = signin_url()
    assert url == CONSOLE_KEYS_URL
    assert url.startswith("https://console.x.ai/")


def test_osc8_and_raw_url() -> None:
    link = SignInLink(url=CONSOLE_KEYS_URL)
    osc = link.osc8()
    assert CONSOLE_KEYS_URL in osc
    assert "\033]8;;" in osc
    assert "Sign in with browser" in osc
    lines = link.display_lines()
    assert lines[0] == osc
    assert lines[1] == CONSOLE_KEYS_URL


def test_build_authorize_url() -> None:
    url = build_authorize_url(
        client_id="client-1",
        redirect_uri="http://127.0.0.1:8765/callback",
        state="st",
        authorize_endpoint="https://example.org/oauth/authorize",
    )
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert parsed.netloc == "example.org"
    assert qs["client_id"] == ["client-1"]
    assert qs["redirect_uri"] == ["http://127.0.0.1:8765/callback"]
    assert qs["response_type"] == ["code"]
    assert qs["state"] == ["st"]


def test_mask_secret_never_full() -> None:
    assert "secret-value-123456" not in mask_secret("secret-value-123456")
    assert mask_secret("secret-value-123456").startswith("secr")
    assert mask_secret("secret-value-123456").endswith("3456")


def test_credential_file_mode_0600(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    path = tmp_path / "credentials"
    store = CredentialStore(path)
    store.save("xai-test-key-abcdefghijklmnopqrstuvwxyz")
    assert path.is_file()
    assert (path.stat().st_mode & 0o777) == 0o600
    loaded = store.load()
    assert loaded["api_key"].startswith("xai-test")
    assert "abcdefghijklmnopqrstuvwxyz" not in loaded["label"]
    store.clear()
    assert not path.exists()


def test_env_key_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XAI_API_KEY", "env-key-value-9999")
    store = CredentialStore(tmp_path / "credentials")
    loaded = store.load()
    assert loaded["source"] == "env"
    assert loaded["api_key"] == "env-key-value-9999"
