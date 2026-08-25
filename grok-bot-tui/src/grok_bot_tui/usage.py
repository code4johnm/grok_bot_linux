"""Local usage meter. Record only what the API actually returned."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from grok_bot_tui.paths import data_dir


def parse_usage(payload: Mapping[str, Any] | None) -> dict[str, int] | None:
    """Return input/output token counts, or None if the API omitted usage."""
    if not payload:
        return None
    raw = payload.get("usage")
    if not isinstance(raw, Mapping):
        return None
    inp = raw.get("input_tokens", raw.get("prompt_tokens"))
    out = raw.get("output_tokens", raw.get("completion_tokens"))
    if inp is None and out is None:
        return None
    try:
        return {"input_tokens": int(inp or 0), "output_tokens": int(out or 0)}
    except (TypeError, ValueError):
        return None


def append_usage_line(
    usage: dict[str, int],
    *,
    session: str,
    model: str,
    path: Path | None = None,
) -> None:
    dest = path if path is not None else data_dir() / "usage.jsonl"
    dest.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "session": session,
        "model": model,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
    }
    with dest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")


def format_meter(last: dict[str, int] | None, total_in: int, total_out: int) -> str:
    if last is None and total_in == 0 and total_out == 0:
        return ""
    parts: list[str] = []
    if last is not None:
        parts.append(f"in:{last['input_tokens']} out:{last['output_tokens']}")
    if total_in or total_out:
        parts.append(f"Σ in:{total_in} out:{total_out}")
    return "  ·  ".join(parts)
