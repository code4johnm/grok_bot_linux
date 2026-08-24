"""Local workspace directory for pid, socket, and prompt history."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def default_workspace_path(environ: dict[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    override = env.get("GROK_BOT_WORKSPACE", "").strip()
    if override:
        return Path(override).expanduser()
    xdg = env.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "grok-bot"
    home = env.get("HOME") or str(Path.home())
    return Path(home) / ".local" / "share" / "grok-bot"


@dataclass
class Workspace:
    root: Path

    @classmethod
    def open(cls, root: Path | None = None) -> Workspace:
        workspace = cls(root=Path(root) if root else default_workspace_path())
        workspace.root.mkdir(parents=True, exist_ok=True)
        workspace.history_path.touch(exist_ok=True)
        return workspace

    @property
    def history_path(self) -> Path:
        return self.root / "history.jsonl"

    @property
    def socket_path(self) -> Path:
        return self.root / "grok-bot.sock"

    @property
    def pid_path(self) -> Path:
        return self.root / "daemon.pid"

    def append_history(self, prompt: str, reply: str) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "prompt": prompt,
            "reply": reply,
        }
        with self.history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def history_count(self) -> int:
        if not self.history_path.is_file():
            return 0
        with self.history_path.open(encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())

    def write_pid(self, pid: int) -> None:
        self.pid_path.write_text(f"{pid}\n", encoding="utf-8")

    def read_pid(self) -> int | None:
        if not self.pid_path.is_file():
            return None
        text = self.pid_path.read_text(encoding="utf-8").strip()
        if not text.isdigit():
            return None
        return int(text)

    def clear_runtime_files(self) -> None:
        for path in (self.pid_path, self.socket_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
