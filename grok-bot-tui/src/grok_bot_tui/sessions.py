"""Local session files. No API keys, no Authorization headers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from grok_bot_tui.paths import data_dir

_NAME_OK = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_SECRET_FIELDS = {"api_key", "authorization", "xai_api_key", "grok_api_key", "token"}


def sanitize_name(raw: str) -> str | None:
    name = raw.strip()
    if not name or not _NAME_OK.match(name):
        return None
    return name


def timestamp_name() -> str:
    return datetime.now(timezone.utc).strftime("session-%Y%m%d-%H%M%S")


def _safe_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in messages:
        role = item.get("role")
        content = item.get("content")
        if role not in ("system", "user", "assistant"):
            continue
        if not isinstance(content, str):
            continue
        out.append({"role": role, "content": content})
    return out


def _strip_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k.lower() not in _SECRET_FIELDS}


class SessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else data_dir() / "sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.root / f"{name}.json"

    def list_names(self) -> list[str]:
        names = [p.stem for p in self.root.glob("*.json") if p.is_file()]
        return sorted(names)

    def save(self, snapshot: dict[str, Any]) -> None:
        name = sanitize_name(str(snapshot.get("name") or ""))
        if name is None:
            raise ValueError("Invalid session name.")
        body = _strip_secrets(
            {
                "name": name,
                "model": snapshot.get("model"),
                "prompt_id": snapshot.get("prompt_id"),
                "notes": list(snapshot.get("notes") or []),
                "messages": _safe_messages(list(snapshot.get("messages") or [])),
                "total_input": int(snapshot.get("total_input") or 0),
                "total_output": int(snapshot.get("total_output") or 0),
            }
        )
        self.path_for(name).write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    def load(self, name: str) -> dict[str, Any] | None:
        clean = sanitize_name(name)
        if clean is None:
            return None
        path = self.path_for(clean)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return _strip_secrets(data)

    def forget(self, name: str) -> bool:
        clean = sanitize_name(name)
        if clean is None:
            return False
        path = self.path_for(clean)
        if not path.is_file():
            return False
        path.unlink()
        return True
