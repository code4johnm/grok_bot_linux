"""Unit tests never spawn grok-bot Electron."""

from __future__ import annotations

import os

os.environ.setdefault("GROK_TUI_NO_ELECTRON", "1")
