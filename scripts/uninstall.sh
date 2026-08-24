#!/usr/bin/env bash
# Wrapper so agents can call scripts/uninstall.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/uninstall.sh" "$@"
