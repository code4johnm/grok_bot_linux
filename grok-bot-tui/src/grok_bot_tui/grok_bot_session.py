"""Grok Bot (Electron GUI) session — not grok CLI, not API keys.

Sign-in happens in the official grok-bot window.
This module does not read Cookies. Session tokens live in grok_bot_auth.py.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from grok_bot_tui.paths import data_dir as tui_data_dir

# Official Grok Bot product surfaces (from the packaged app / x.ai/bot).
BOT_HOME_URL = "https://x.ai/bot"
BOT_ONBOARDING_URL = "https://cursor.com/bot/onboarding"
BOT_AGENTS_URL = "https://cursor.com/agents/"

# Public teammate templates from x.ai/bot ("Give each Bot a job").
# Private operator bots live in the Grok Bot app; this list is not scraped.
STARTER_BOTS = (
    ("sales-outbound", "Sales Outbound", "Pipeline overnight, drafts to approve"),
    ("talent-scout", "Talent Scout", "Sourcing and outreach"),
    ("paid-media", "Paid Media", "Campaign ops"),
    ("expense-manager", "Expense Manager", "Inbox to ledger"),
    ("product-performance", "Product Performance", "Product metrics and follow-up"),
    ("bug-repro", "Bug Reproduction", "Repro, ticket, handoff"),
    ("account-health", "Account Health", "Accounts that need attention"),
    ("chief-of-staff", "Chief of Staff", "Coordinate other bots"),
)

_SCOPE_HASH_RE = re.compile(r'"hasSeenOnboardingAccountScope"\s*:\s*"([^"]+)"')
_SCOPES_NONEMPTY_RE = re.compile(r'"accountScopes"\s*:\s*\{[^\s}]')


def config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "Grok Bot"


def data_dir() -> Path:
    env = os.environ.get("GROK_BOT_DATA", "").strip()
    if env:
        return Path(env)
    return Path.home() / ".grokbot"


def ignore_gui_session_path() -> Path:
    """TUI-only opt-out. Never written into the Grok Bot Electron profile."""
    return tui_data_dir() / "ignore-gui-session"


def set_ignore_gui_session(ignored: bool) -> None:
    path = ignore_gui_session_path()
    if ignored:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("1\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return
    if path.is_file():
        path.unlink()


def gui_session_ignored() -> bool:
    return ignore_gui_session_path().is_file()


def _leveldb_bytes(folder: Path) -> int:
    if not folder.is_dir():
        return 0
    total = 0
    try:
        for item in folder.iterdir():
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def session_looks_signed_in(*, cfg: Path | None = None, data: Path | None = None) -> bool:
    """Heuristic: Electron user-data after a real GUI login. No cookie parse."""
    cfg = cfg or config_dir()
    data = data or data_dir()
    settings = data / "settings.json"
    if settings.is_file():
        try:
            text = settings.read_text(encoding="utf-8")
        except OSError:
            text = ""
        match = _SCOPE_HASH_RE.search(text)
        if match and len(match.group(1).strip()) >= 16:
            return True
        if _SCOPES_NONEMPTY_RE.search(text):
            return True
    ls = _leveldb_bytes(cfg / "Local Storage" / "leveldb")
    ss = _leveldb_bytes(cfg / "Session Storage")
    return ls > 2048 or ss > 1024


@dataclass(frozen=True)
class BotIdentity:
    signed_in: bool
    label: str = "Grok Bot GUI"


def load_identity(*, cfg: Path | None = None, data: Path | None = None) -> BotIdentity:
    if gui_session_ignored():
        return BotIdentity(signed_in=False, label="")
    if session_looks_signed_in(cfg=cfg, data=data):
        return BotIdentity(signed_in=True, label="Grok Bot GUI session")
    return BotIdentity(signed_in=False, label="")


def starter_bots() -> list[dict[str, str]]:
    """Public x.ai/bot templates only. Not the signed-in roster."""
    return [{"id": i, "name": n, "blurb": b} for i, n, b in STARTER_BOTS]


_ACCOUNT_SLOT_KEY = "sand.client.slice.client-meta.account-slot"


def persistence_dir(cfg: Path | None = None) -> Path:
    return (cfg or config_dir()) / "sand-client-persistence"


def persistence_blob_name(key: str) -> str:
    token = base64.b32encode(key.encode("utf-8")).decode("ascii").rstrip("=").lower()
    return f"{token}.blob"


def _decode_blob_name(name: str) -> str | None:
    stem = name[:-5] if name.endswith(".blob") else name
    pad = "=" * ((8 - len(stem) % 8) % 8)
    try:
        return base64.b32decode(stem.upper() + pad, casefold=True).decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def _read_json_file(path: Path) -> Any:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return raw


def _slice_value(path: Path) -> Any:
    raw = _read_json_file(path)
    if isinstance(raw, dict) and "value" in raw:
        return raw.get("value")
    return raw


def _iter_slices(cfg: Path | None = None) -> list[tuple[str, Path]]:
    folder = persistence_dir(cfg)
    if not folder.is_dir():
        return []
    rows: list[tuple[str, Path]] = []
    try:
        items = list(folder.iterdir())
    except OSError:
        return []
    for path in items:
        if not path.is_file() or not path.name.endswith(".blob"):
            continue
        key = _decode_blob_name(path.name)
        if key:
            rows.append((key, path))
    return rows


def _account_slot(cfg: Path | None = None) -> str:
    for key, path in _iter_slices(cfg):
        if key == _ACCOUNT_SLOT_KEY:
            value = _slice_value(path)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _account_key_prefix(slot: str) -> str:
    encoded = urllib.parse.quote(slot, safe="")
    return f"sand.client.slice.account.{encoded}."


def _find_slice(suffix: str, cfg: Path | None = None) -> Path | None:
    slot = _account_slot(cfg)
    prefix = _account_key_prefix(slot) if slot else ""
    slices = _iter_slices(cfg)

    def newest(keys_ok: Callable[[str], bool]) -> Path | None:
        matched: list[tuple[float, Path]] = []
        for key, path in slices:
            if not key.endswith(suffix) or not keys_ok(key):
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            matched.append((mtime, path))
        if not matched:
            return None
        matched.sort(key=lambda item: item[0], reverse=True)
        return matched[0][1]

    if prefix:
        hit = newest(lambda key: key.startswith(prefix))
        if hit is not None:
            return hit
    return newest(lambda _key: True)


def _one_line(text: str, limit: int = 40) -> str:
    line = re.sub(r"\s+", " ", text).strip()
    if not line:
        return ""
    if len(line) <= limit:
        return line
    return line[: limit - 1] + "…"


def _bot_blurb(row: dict[str, Any]) -> str:
    unread = 0
    try:
        unread = int(row.get("unreadCount") or 0)
    except (TypeError, ValueError):
        unread = 0
    desc = row.get("description")
    blurb = _one_line(desc if isinstance(desc, str) else "")
    if unread > 0 and blurb:
        return f"{unread} unread · {blurb}"
    if unread > 0:
        return f"{unread} unread"
    if row.get("isGroup") and not blurb:
        return "group"
    return blurb or "bot"


def last_selected_agent_id(*, cfg: Path | None = None) -> str:
    path = _find_slice(".selection.last-agent", cfg)
    if path is None:
        return ""
    value = _slice_value(path)
    if not isinstance(value, dict):
        return ""
    ident = str(value.get("agentId") or "").strip()
    return ident


def _pinned_agent_ids(*, cfg: Path | None = None) -> list[str]:
    path = _find_slice(".ui-agent-refs", cfg)
    if path is None:
        return []
    value = _slice_value(path)
    if not isinstance(value, dict):
        return []
    raw = value.get("pinnedAgentIds")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def session_bots(*, cfg: Path | None = None) -> list[dict[str, str]]:
    """Bots from the signed-in Grok Bot roster cache. No Cookies / no secrets files."""
    path = _find_slice(".roster.last-roster", cfg)
    if path is None:
        return []
    value = _slice_value(path)
    if not isinstance(value, dict):
        return []
    rows = value.get("rows")
    if not isinstance(rows, list):
        return []
    bots: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("isHiddenFromSidebar") is True:
            continue
        ident = str(row.get("id") or "").strip()
        name = str(row.get("name") or row.get("title") or "").strip()
        if not ident or not name or ident in seen:
            continue
        seen.add(ident)
        desc = row.get("description")
        instructions = _one_line(desc if isinstance(desc, str) else "", limit=1200)
        bots.append(
            {
                "id": ident,
                "name": name,
                "blurb": _bot_blurb(row),
                "instructions": instructions,
            }
        )
    pinned = _pinned_agent_ids(cfg=cfg)
    if pinned:
        order = {ident: i for i, ident in enumerate(pinned)}
        bots.sort(key=lambda bot: (0, order[bot["id"]]) if bot["id"] in order else (1, 0))
    return bots


def wait_for_gui_session(
    *,
    timeout: float = 20.0,
    interval: float = 1.0,
    check: Callable[[], bool] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> bool:
    """Poll the GUI-session heuristic. Does not read Cookies."""
    looks_in = check or session_looks_signed_in
    if looks_in():
        return True
    if timeout <= 0:
        return False
    pause = sleep or time.sleep
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pause(interval)
        if looks_in():
            return True
    return looks_in()
