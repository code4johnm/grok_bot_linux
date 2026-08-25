"""Official grok CLI (Grok Build TUI). Flags come from `grok --help` only."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

# Flags John listed from official `grok --help` ("Grok Build TUI"). Not invented extras.
DOCUMENTED_GROK_FLAGS = frozenset(
    {
        "--help",
        "--agent",
        "--allow",
        "--deny",
        "--always-approve",
        "--continue",
        "--no-plan",
        "--no-subagents",
        "--model",
    }
)

_FLAG = re.compile(r"(--[a-z0-9][a-z0-9-]*)")
_SECRET_NAMES = frozenset({"auth.json", "credentials", "credentials.json", "token", "secret"})


def find_grok(extra: Sequence[Path] | None = None) -> Path | None:
    env = os.environ.get("GROK_BIN", "").strip()
    paths: list[Path] = []
    if extra:
        paths.extend(extra)
    if env:
        paths.append(Path(env))
    which = shutil.which("grok")
    if which:
        paths.append(Path(which))
    paths.append(Path.home() / ".grok/bin/grok")
    for path in paths:
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def grok_help_text(
    binary: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> str:
    run = runner or subprocess.run
    try:
        proc = run(
            [str(binary), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"Could not run {binary} --help: {exc}") from exc
    return (proc.stdout or "") + (proc.stderr or "")


def flags_from_help(help_text: str) -> set[str]:
    found = set(_FLAG.findall(help_text or ""))
    return found or set(DOCUMENTED_GROK_FLAGS)


def validate_grok_args(args: Sequence[str], allowed: set[str]) -> str | None:
    """Reject invented --flags. Values after a known flag are allowed."""
    i = 0
    items = list(args)
    while i < len(items):
        token = items[i]
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            if name not in allowed:
                return f"Unknown grok flag {name}. Pass-through only uses flags from grok --help."
            if "=" not in token and i + 1 < len(items) and not items[i + 1].startswith("-"):
                i += 2
                continue
        elif token.startswith("-") and token != "-":
            return f"Unknown grok flag {token}. Pass-through only uses flags from grok --help."
        i += 1
    return None


def missing_grok_message() -> str:
    return (
        "Official grok CLI not found (Grok Build TUI). "
        "Install with ./scripts/install-cli.sh or https://x.ai/cli/install.sh. "
        "Expected on PATH or ~/.grok/bin/grok."
    )


def summarize_grok_home(root: Path | None = None) -> str:
    """Read-only listing of ~/.grok. Never opens auth.json or credentials."""
    home = Path(root) if root is not None else Path.home() / ".grok"
    if not home.is_dir():
        return "No ~/.grok directory. Official grok sessions live there after CLI install."
    lines = ["Official ~/.grok (read-only; credentials skipped):"]
    try:
        entries = sorted(home.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        return f"Could not read ~/.grok: {exc}"
    for path in entries:
        if path.name.lower() in _SECRET_NAMES or path.suffix.lower() in {".pem", ".key"}:
            lines.append(f"  {path.name}  (skipped)")
            continue
        mark = "/" if path.is_dir() else ""
        lines.append(f"  {path.name}{mark}")
    return "\n".join(lines)


def run_grok(
    binary: Path,
    args: Sequence[str],
    *,
    runner: Callable[..., int] | None = None,
) -> int:
    cmd = [str(binary), *args]
    if runner is not None:
        return int(runner(cmd))
    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)
