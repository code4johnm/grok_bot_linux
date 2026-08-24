"""Environment-only configuration. API keys are never written to disk."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_API_BASE = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-4"
DEFAULT_TIMEOUT = 120.0


class ConfigError(RuntimeError):
    """User-facing configuration problem."""


def read_api_key(environ: dict[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    for name in ("GROK_API_KEY", "XAI_API_KEY"):
        value = env.get(name, "").strip()
        if value:
            return value
    raise ConfigError(
        "Set GROK_API_KEY or XAI_API_KEY in the environment. "
        "Do not put the key in this repository."
    )


def api_key_present(environ: dict[str, str] | None = None) -> bool:
    try:
        read_api_key(environ)
    except ConfigError:
        return False
    return True


@dataclass(frozen=True)
class Settings:
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> Settings:
        env = os.environ if environ is None else environ
        timeout_raw = env.get("GROK_TIMEOUT", "").strip()
        timeout = float(timeout_raw) if timeout_raw else DEFAULT_TIMEOUT
        return cls(
            api_base=env.get("GROK_API_BASE", DEFAULT_API_BASE).strip() or DEFAULT_API_BASE,
            model=env.get("GROK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            timeout=timeout,
        )
