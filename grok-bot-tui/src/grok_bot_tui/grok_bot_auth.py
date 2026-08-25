"""Grok Bot (Cursor) session tokens from the desktop secret store.

Reads `$HOME/.config/Grok Bot/sand-secrets.json` `cursor-accounts`.
Does not read Cookies. Never logs the token.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
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


def _b64decode(blob: str) -> bytes | None:
    pad = "=" * ((4 - len(blob) % 4) % 4)
    for candidate in (blob, blob + pad):
        try:
            return base64.b64decode(candidate)
        except (OSError, ValueError):
            continue
    return None


def _libsecret_passwords() -> list[bytes]:
    out: list[bytes] = []
    lookups = (
        ("application", "Grok Bot"),
        ("application", "grok-bot"),
        ("application", "Chrome"),
        ("application", "Chromium"),
        ("xdg:schema", "chrome_libsecret_os_crypt_password_v2"),
    )
    for key, value in lookups:
        try:
            proc = subprocess.run(
                ["secret-tool", "lookup", key, value],
                capture_output=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        pw = proc.stdout.strip()
        if proc.returncode == 0 and pw:
            out.append(pw)
    extra = os.environ.get("GROK_BOT_SAFE_STORAGE_KEY", "").strip()
    if extra:
        out.append(extra.encode("utf-8"))
    # Chromium defaults used when the OS store is missing.
    out.extend([b"peanuts", b""])
    seen: set[bytes] = set()
    uniq: list[bytes] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            uniq.append(item)
    return uniq


def _unpad_pkcs7(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
        return data[:-pad]
    return data


def _looks_like_token(text: str) -> bool:
    if len(text) < 16:
        return False
    if any(ch in text for ch in "\x00\r"):
        return False
    return True


def _decrypt_os_crypt(blob: str, password: bytes) -> str | None:
    raw = _b64decode(blob)
    if raw is None or len(raw) < 20:
        return None
    if raw.startswith(b"v10") or raw.startswith(b"v11"):
        data = raw[3:]
    else:
        data = raw
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except Exception:
        return None
    key = hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1, 16)
    backend = default_backend()
    # v10/v11 AES-128-CBC, IV of 16 spaces (Chromium Linux).
    if len(data) >= 16 and len(data) % 16 == 0:
        try:
            decryptor = Cipher(algorithms.AES(key), modes.CBC(b" " * 16), backend=backend).decryptor()
            plain = _unpad_pkcs7(decryptor.update(data) + decryptor.finalize())
            text = plain.decode("utf-8")
            if _looks_like_token(text):
                return text
        except Exception:
            pass
    # v11 AES-128-GCM: 12-byte nonce, 16-byte tag.
    if len(data) > 28:
        nonce, rest = data[:12], data[12:]
        tag, ct = rest[-16:], rest[:-16]
        try:
            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag), backend=backend).decryptor()
            text = (decryptor.update(ct) + decryptor.finalize()).decode("utf-8")
            if _looks_like_token(text):
                return text
        except Exception:
            pass
    return None


def _decode_stored(value: str) -> str | None:
    if not value:
        return None
    if value.startswith(PLAINTEXT_PREFIX):
        blob = value[len(PLAINTEXT_PREFIX) :]
        raw = _b64decode(blob)
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if value.startswith(SCOPED_PREFIX):
        rest = value[len(SCOPED_PREFIX) :]
        _, sep, cipher = rest.partition(":")
        if not sep:
            return None
        value = cipher
    for password in _libsecret_passwords():
        got = _decrypt_os_crypt(value, password)
        if got:
            return got
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
