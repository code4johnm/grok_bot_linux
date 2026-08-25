"""Grok Bot (Cursor) session tokens from the desktop secret store.

Reads `$HOME/.config/Grok Bot/sand-secrets.json` `cursor-accounts`.
Does not read Cookies. Never logs the token.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from grok_bot_tui.grok_bot_session import config_dir

PLAINTEXT_PREFIX = "plaintext:v1:"
SCOPED_PREFIX = "scoped:v1:"
ACCESS_KEY = "cursor-access-token"
REFRESH_KEY = "cursor-refresh-token"
ACCOUNTS_KEY = "cursor-accounts"


def secrets_path(*, cfg: Path | None = None) -> Path:
    override = os.environ.get("GROK_BOT_SECRETS", "").strip()
    if override:
        return Path(override)
    return (cfg or config_dir()) / "sand-secrets.json"


def _decode_stored(value: str) -> str | None:
    if not value:
        return None
    if value.startswith(PLAINTEXT_PREFIX):
        blob = value[len(PLAINTEXT_PREFIX) :]
        try:
            return base64.b64decode(blob).decode("utf-8")
        except (OSError, ValueError, UnicodeDecodeError):
            try:
                return base64.b64decode(blob + "=" * ((4 - len(blob) % 4) % 4)).decode("utf-8")
            except (OSError, ValueError, UnicodeDecodeError):
                return None
    if value.startswith(SCOPED_PREFIX):
        # scoped:v1:<64-hex-scope>:<ciphertext-b64> — ciphertext still OS-encrypted.
        return None
    # v10/v11 Electron safeStorage blobs stay in the desktop store.
    return None


def _accounts_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    blob = raw.get(ACCOUNTS_KEY)
    if isinstance(blob, dict):
        return blob
    if not isinstance(blob, str) or not blob.strip():
        return None
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def load_access_token(*, cfg: Path | None = None) -> str | None:
    """Return the signed-in Grok Bot access token, or None. Never log it."""
    env = os.environ.get("GROK_BOT_ACCESS_TOKEN", "").strip()
    if env:
        return env
    path = secrets_path(cfg=cfg)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    rec = _accounts_record(raw)
    if rec is None:
        return None
    active = rec.get("active")
    accounts = rec.get("accounts")
    if not isinstance(accounts, dict) or not accounts:
        return None
    slot = accounts.get(active) if isinstance(active, str) and active in accounts else None
    if not isinstance(slot, dict):
        slot = next((v for v in accounts.values() if isinstance(v, dict)), None)
    if not isinstance(slot, dict):
        return None
    stored = str(slot.get(ACCESS_KEY) or "").strip()
    decoded = _decode_stored(stored)
    if decoded:
        return decoded
    # Encrypted desktop blob (v10/v11). Caller should keep using the GUI session
    # until a plaintext token is available; do not scrape Cookies.
    return None


def has_grok_bot_creds(*, cfg: Path | None = None) -> bool:
    if os.environ.get("GROK_BOT_ACCESS_TOKEN", "").strip():
        return True
    path = secrets_path(cfg=cfg)
    if not path.is_file():
        return False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    rec = _accounts_record(raw) if isinstance(raw, dict) else None
    if rec is None:
        return False
    accounts = rec.get("accounts")
    if not isinstance(accounts, dict):
        return False
    for slot in accounts.values():
        if isinstance(slot, dict) and str(slot.get(ACCESS_KEY) or "").strip():
            return True
    return False
