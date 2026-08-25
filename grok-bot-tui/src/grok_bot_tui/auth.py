"""Sign-in: OSC 8 link, loopback catcher, API-key store. No cookie scraping."""

from __future__ import annotations

import json
import os
import secrets
import stat
import threading
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

# Official console (no public third-party OAuth client for companion apps).
CONSOLE_LOGIN_URL = "https://console.x.ai/login"
CONSOLE_KEYS_URL = "https://console.x.ai/team/default/api-keys"
DEFAULT_AUTHORIZE_URL = "https://accounts.x.ai/sign-in"


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


def signin_url(*, keys: bool = True) -> str:
    """Official page to create/copy an API key (docs.x.ai quickstart)."""
    override = os.environ.get("GROK_TUI_SIGNIN_URL", "").strip()
    if override:
        return override
    return CONSOLE_KEYS_URL if keys else CONSOLE_LOGIN_URL


def build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    authorize_endpoint: str | None = None,
) -> str:
    """PKCE/authorize URL builder. Used when XAI_OAUTH_CLIENT_ID is set."""
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


class LoopbackCatcher:
    """127.0.0.1 ephemeral server. Accepts ?api_key= or ?code= on /callback."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self._wanted_port = port
        self.httpd: HTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.event = threading.Event()
        self.result: dict[str, str] = {}
        self.state = secrets.token_urlsafe(16)

    @property
    def port(self) -> int:
        if self.httpd is None:
            return 0
        return int(self.httpd.server_address[1])

    @property
    def callback_url(self) -> str:
        return f"http://{self.host}:{self.port}/callback"

    def start(self) -> str:
        catcher = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path not in ("/callback", "/", "/login"):
                    self.send_error(404)
                    return
                qs = parse_qs(parsed.query)
                payload: dict[str, str] = {}
                for name in ("api_key", "key", "code", "state", "error"):
                    vals = qs.get(name)
                    if vals:
                        payload[name] = vals[0]
                catcher.result = payload
                catcher.event.set()
                body = b"<html><body>You can close this tab and return to Grok GUI TUI shell.</body></html>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt: str, *args: object) -> None:
                return

        self.httpd = HTTPServer((self.host, self._wanted_port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.callback_url

    def wait(self, timeout: float = 180.0) -> dict[str, str]:
        self.event.wait(timeout)
        return dict(self.result)

    def stop(self) -> None:
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def open_browser(url: str, opener: Callable[[str], bool] | None = None) -> bool:
    open_fn = opener or webbrowser.open
    try:
        return bool(open_fn(url))
    except Exception:
        return False
