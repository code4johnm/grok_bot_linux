#!/usr/bin/env bash
# TUI-only wrapper. Delegates to grok-bot-tui/install.sh (Ubuntu/Kali/Rocky/Pi).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/grok-bot-tui/install.sh" --tui-only "$@"
