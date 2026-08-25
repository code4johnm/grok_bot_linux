"""Durable session directories. No API keys, no Authorization headers."""

from __future__ import annotations

import json
import re
import shutil
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
    """Each session is a directory: state.json, notes.txt, transcript.json."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else data_dir() / "sessions"
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def current_path(self) -> Path:
        return self.root.parent / "current"

    def path_for(self, name: str) -> Path:
        return self.root / name

    def state_path(self, name: str) -> Path:
        return self.path_for(name) / "state.json"

    def list_names(self) -> list[str]:
        names = [
            p.name
            for p in self.root.iterdir()
            if p.is_dir() and (p / "state.json").is_file()
        ]
        return sorted(names)

    def current_name(self) -> str | None:
        if not self.current_path.is_file():
            return None
        name = sanitize_name(self.current_path.read_text(encoding="utf-8"))
        return name

    def set_current(self, name: str) -> None:
        clean = sanitize_name(name)
        if clean is None:
            return
        self.current_path.parent.mkdir(parents=True, exist_ok=True)
        self.current_path.write_text(clean + "\n", encoding="utf-8")

    def save(self, snapshot: dict[str, Any]) -> None:
        name = sanitize_name(str(snapshot.get("name") or ""))
        if name is None:
            raise ValueError("Invalid session name.")
        dest = self.path_for(name)
        dest.mkdir(parents=True, exist_ok=True)
        notes = [str(n) for n in (snapshot.get("notes") or [])]
        state = _strip_secrets(
            {
                "name": name,
                "model": snapshot.get("model"),
                "prompt_id": snapshot.get("prompt_id"),
                "total_input": int(snapshot.get("total_input") or 0),
                "total_output": int(snapshot.get("total_output") or 0),
                "plans_approved": int(snapshot.get("plans_approved") or 0),
                "plans_cancelled": int(snapshot.get("plans_cancelled") or 0),
                "pending_plan": snapshot.get("pending_plan")
                if isinstance(snapshot.get("pending_plan"), str)
                else None,
            }
        )
        self.state_path(name).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        (dest / "notes.txt").write_text(("\n".join(notes) + "\n") if notes else "", encoding="utf-8")
        (dest / "transcript.json").write_text(
            json.dumps(_safe_messages(list(snapshot.get("messages") or [])), indent=2) + "\n",
            encoding="utf-8",
        )
        self.set_current(name)

    def load(self, name: str) -> dict[str, Any] | None:
        clean = sanitize_name(name)
        if clean is None:
            return None
        path = self.state_path(clean)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        notes_path = self.path_for(clean) / "notes.txt"
        notes: list[str] = []
        if notes_path.is_file():
            notes = [line for line in notes_path.read_text(encoding="utf-8").splitlines() if line]
        transcript_path = self.path_for(clean) / "transcript.json"
        messages: list[dict[str, str]] = []
        if transcript_path.is_file():
            try:
                raw = json.loads(transcript_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                raw = []
            if isinstance(raw, list):
                messages = _safe_messages(raw)
        data = _strip_secrets(data)
        data["notes"] = notes
        data["messages"] = messages
        data["name"] = clean
        return data

    def forget(self, name: str) -> bool:
        clean = sanitize_name(name)
        if clean is None:
            return False
        dest = self.path_for(clean)
        if not dest.is_dir():
            return False
        shutil.rmtree(dest)
        if self.current_name() == clean:
            self.current_path.unlink(missing_ok=True)
        return True
