"""Grok.com / Grok Bot identity via official grok CLI (OIDC/SSO). No cookie scrape."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEVICE_URL_RE = re.compile(
    r"https://accounts\.x\.ai/oauth2/device\?user_code=[A-Z0-9-]+",
    re.IGNORECASE,
)
USER_CODE_RE = re.compile(r"\b([A-Z0-9]{4,}-[A-Z0-9]{4,})\b")
SIGN_IN_URL = "https://accounts.x.ai/sign-in"


def grok_home() -> Path:
    env = os.environ.get("GROK_HOME", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".grok"


def find_grok_cli() -> Path | None:
    which = shutil.which("grok")
    if which:
        return Path(which)
    candidate = grok_home() / "bin" / "grok"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


@dataclass(frozen=True)
class GrokIdentity:
    email: str = ""
    first_name: str = ""
    user_id: str = ""
    auth_mode: str = ""
    issuer: str = ""
    expires_at: str = ""

    @property
    def signed_in(self) -> bool:
        return bool(self.email or self.user_id)

    @property
    def label(self) -> str:
        if self.first_name and self.email:
            return f"{self.first_name} ({_mask_email(self.email)})"
        if self.email:
            return _mask_email(self.email)
        if self.first_name:
            return self.first_name
        if self.user_id:
            return self.user_id[:8] + "…"
        return "grok.com session"


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email[:1] + "…" if email else ""
    local, _, domain = email.partition("@")
    if not local:
        return "…@" + domain
    return local[0] + "***@" + domain


def load_identity(path: Path | None = None) -> GrokIdentity | None:
    """Read official grok CLI auth.json. Never returns the token."""
    auth_path = path or (grok_home() / "auth.json")
    if not auth_path.is_file():
        return None
    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not raw:
        return None
    inner = next(iter(raw.values()))
    if not isinstance(inner, dict):
        return None
    if not inner.get("key") and not inner.get("refresh_token"):
        return None
    return GrokIdentity(
        email=str(inner.get("email") or ""),
        first_name=str(inner.get("first_name") or ""),
        user_id=str(inner.get("user_id") or ""),
        auth_mode=str(inner.get("auth_mode") or ""),
        issuer=str(inner.get("oidc_issuer") or ""),
        expires_at=str(inner.get("expires_at") or ""),
    )


def session_bearer(path: Path | None = None) -> str | None:
    """Access token for grok.com session APIs. Caller must not log it."""
    auth_path = path or (grok_home() / "auth.json")
    if not auth_path.is_file():
        return None
    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or not raw:
        return None
    inner = next(iter(raw.values()))
    if not isinstance(inner, dict):
        return None
    key = str(inner.get("key") or "").strip()
    return key or None


@dataclass(frozen=True)
class DevicePrompt:
    url: str
    user_code: str


def parse_device_login_output(text: str) -> DevicePrompt | None:
    match = DEVICE_URL_RE.search(text)
    if not match:
        return None
    url = match.group(0)
    code = ""
    qs = re.search(r"user_code=([A-Z0-9-]+)", url, re.I)
    if qs:
        code = qs.group(1)
    else:
        codes = USER_CODE_RE.findall(text)
        code = codes[-1] if codes else ""
    return DevicePrompt(url=url, user_code=code)


def load_cached_models(path: Path | None = None) -> list[dict[str, str]]:
    """Model list from grok CLI cache. Drops api_key and other secrets."""
    cache = path or (grok_home() / "models_cache.json")
    if not cache.is_file():
        return []
    try:
        raw = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    models = raw.get("models") if isinstance(raw, dict) else None
    if not isinstance(models, dict):
        return []
    rows: list[dict[str, str]] = []
    for mid, meta in models.items():
        info: dict[str, Any] = {}
        if isinstance(meta, dict):
            maybe = meta.get("info")
            if isinstance(maybe, dict):
                info = maybe
        name = str(info.get("name") or mid)
        blurb = str(info.get("description") or info.get("model_family") or "Grok model")
        rows.append({"id": str(info.get("id") or mid), "name": name, "blurb": blurb})
    return rows


def start_device_login(cli: Path | None = None) -> subprocess.Popen[str]:
    """Official `grok login --device-auth` (SSO in browser, same as Grok Bot)."""
    binary = cli or find_grok_cli()
    if binary is None:
        raise FileNotFoundError("grok CLI not found")
    return subprocess.Popen(
        [str(binary), "login", "--device-auth"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def grok_logout(cli: Path | None = None) -> bool:
    binary = cli or find_grok_cli()
    if binary is None:
        return False
    try:
        proc = subprocess.run(
            [str(binary), "logout"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0
