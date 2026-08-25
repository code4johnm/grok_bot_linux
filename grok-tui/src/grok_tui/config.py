"""CLI flags and environment configuration. Never logs secrets."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

# Current chat model in https://docs.x.ai/developers/quickstart (2026).
DEFAULT_MODEL = "grok-4.6"
DEFAULT_BASE_URL = "https://api.x.ai/v1"
DEFAULT_SYSTEM = "You are a short, helpful assistant in a terminal."
# Reasoning models: docs.x.ai generate-text / streaming recommend a long timeout.
DEFAULT_TIMEOUT = 3600.0


class MissingAPIKeyError(Exception):
    """Raised when no API key is configured."""

    def __init__(self) -> None:
        super().__init__(
            "Missing API key. Set XAI_API_KEY or GROK_API_KEY "
            "(or pass --api-key). Never commit the value."
        )


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    system: str
    timeout: float
    base_url: str


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _parse_timeout(raw: str | None, fallback: float) -> float:
    if raw is None or raw.strip() == "":
        return fallback
    try:
        timeout = float(raw)
    except ValueError as exc:
        raise SystemExit(f"Invalid timeout: {raw!r}") from exc
    if timeout <= 0:
        raise SystemExit("Timeout must be greater than 0.")
    return timeout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grok-tui",
        description="Minimal TUI chat with Grok via the xAI Responses API.",
    )
    parser.add_argument(
        "--api-key",
        dest="api_key",
        default=None,
        help="API key (prefer XAI_API_KEY or GROK_API_KEY).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Model ID (default: {DEFAULT_MODEL} or GROK_MODEL).",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="System prompt (default: GROK_SYSTEM or a short terminal assistant).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT:g} or GROK_TIMEOUT).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help=f"API base URL (default: {DEFAULT_BASE_URL}).",
    )
    return parser


def load_config(argv: list[str] | None = None) -> Config:
    args = build_parser().parse_args(argv)
    api_key = (args.api_key or "").strip() or _first_env("XAI_API_KEY", "GROK_API_KEY")
    if not api_key:
        raise MissingAPIKeyError()

    timeout = args.timeout
    if timeout is None:
        timeout = _parse_timeout(os.environ.get("GROK_TIMEOUT"), DEFAULT_TIMEOUT)
    elif timeout <= 0:
        raise SystemExit("Timeout must be greater than 0.")

    return Config(
        api_key=api_key,
        model=(args.model or _first_env("GROK_MODEL") or DEFAULT_MODEL),
        system=(args.system if args.system is not None else (_first_env("GROK_SYSTEM") or DEFAULT_SYSTEM)),
        timeout=timeout,
        base_url=(args.base_url or _first_env("GROK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
    )
