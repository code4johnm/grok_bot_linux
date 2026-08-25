"""Links, optional API-key file store. Grok Bot GUI SSO lives in grok_bot_session."""

from __future__ import annotations

import json
import os
import stat
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from grok_bot_tui.grok_bot_session import BOT_ONBOARDING_URL

# Official console (API-key fallback only — not Grok Bot SSO).
CONSOLE_LOGIN_URL = "https://console.x.ai/login"
CONSOLE_KEYS_URL = "https://console.x.ai/team/default/api-keys"
# Same onboarding URL the grok-bot Electron app uses.
DEFAULT_AUTHORIZE_URL = BOT_ONBOARDING_URL


@dataclass(frozen=True)
class SignInLink:
    url: str
    label: str = "Sign in with browser"

    def osc8(self) -> str:
        return f"\033]8;;{self.url}\033\\{self.label}\033]8;;\033\\"

    def display_lines(self) -> list[str]:
        return [
            self.osc8(),
            self.url,
        ]


def signin_url(*, keys: bool = False) -> str:
    """Grok Bot GUI onboarding (Cursor SSO). keys=True is the API-key console only."""
    override = os.environ.get("GROK_TUI_SIGNIN_URL", "").strip()
    if override:
        return override
    if keys:
        return CONSOLE_KEYS_URL
    return DEFAULT_AUTHORIZE_URL


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    authorize_endpoint: str | None = None,
) -> str:
    """OAuth authorize URL builder for a future public client.

    Default /login launches grok-bot and OSC 8 to Cursor onboarding.
    """
    base = (
        authorize_endpoint
        or os.environ.get("XAI_OAUTH_AUTHORIZE_URL", "").strip()
        or DEFAULT_AUTHORIZE_URL
    )
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": os.environ.get("XAI_OAUTH_SCOPE", "api"),
        }
    )
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{query}"


def mask_secret(value: str | None) -> str:
    if not value:
        return "(none)"
    text = value.strip()
    if len(text) <= 8:
        return "…"
    return f"{text[:4]}…{text[-4:]}"


def credentials_path() -> Path:
    override = os.environ.get("GROK_TUI_CREDENTIALS", "").strip()
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "grok-tui-shell" / "credentials"


class CredentialStore:
    """API key store: optional keyring, else 0600 file. Never logs the secret."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or credentials_path()

    def load(self) -> dict[str, Any]:
        env = os.environ.get("XAI_API_KEY", "").strip() or os.environ.get("GROK_API_KEY", "").strip()
        if env:
            return {"api_key": env, "source": "env", "label": mask_secret(env)}
        ring = self._keyring_get()
        if ring:
            return {"api_key": ring, "source": "keyring", "label": mask_secret(ring)}
        data = self._file_load()
        key = str(data.get("api_key") or "").strip()
        if key:
            return {"api_key": key, "source": "file", "label": mask_secret(key)}
        return {}

    def save(self, api_key: str, *, extra: dict[str, Any] | None = None) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError("empty credential")
        self._file_save(key, extra or {})
        self._keyring_set(key)

    def clear(self) -> None:
        self._keyring_delete()
        if self.path.is_file():
            self.path.unlink()

    def _file_load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _file_save(self, api_key: str, extra: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"api_key": api_key, **{k: v for k, v in extra.items() if k != "api_key"}}
        self.path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)

    def _keyring_get(self) -> str | None:
        try:
            import keyring  # type: ignore[import-untyped]
        except Exception:
            return None
        try:
            value = keyring.get_password("grok-tui-shell", "api_key")
        except Exception:
            return None
        return value.strip() if isinstance(value, str) and value.strip() else None

    def _keyring_set(self, api_key: str) -> bool:
        try:
            import keyring  # type: ignore[import-untyped]
        except Exception:
            return False
        try:
            keyring.set_password("grok-tui-shell", "api_key", api_key)
        except Exception:
            return False
        return True

    def _keyring_delete(self) -> None:
        try:
            import keyring  # type: ignore[import-untyped]
        except Exception:
            return
        try:
            keyring.delete_password("grok-tui-shell", "api_key")
        except Exception:
            return


def open_browser(url: str, opener: Callable[[str], bool] | None = None) -> bool:
    open_fn = opener or webbrowser.open
    try:
        return bool(open_fn(url))
    except Exception:
        return False
