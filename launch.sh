#!/usr/bin/env bash
# Portable launcher for the community Linux port of Grok Bot (Electron).
set -euo pipefail

_resolve_root() {
  local src="${BASH_SOURCE[0]}"
  while [[ -h "$src" ]]; do
    local dir
    dir="$(cd -P "$(dirname "$src")" && pwd)"
    src="$(readlink "$src")"
    [[ "$src" != /* ]] && src="$dir/$src"
  done
  cd -P "$(dirname "$src")" && pwd
}

ROOT="$(_resolve_root)"

find_app_dir() {
  if [[ -n "${GROK_BOT_HOME:-}" && -x "${GROK_BOT_HOME}/grok-bot" ]]; then
    printf '%s\n' "$GROK_BOT_HOME"
    return 0
  fi
  if [[ -x "$ROOT/app/grok-bot" ]]; then
    printf '%s\n' "$ROOT/app"
    return 0
  fi
  if [[ -x "$ROOT/grok-bot" && -f "$ROOT/chrome_100_percent.pak" ]]; then
    printf '%s\n' "$ROOT"
    return 0
  fi
  if [[ -x "${HOME}/.local/opt/Grok_Bot/grok-bot" ]]; then
    printf '%s\n' "${HOME}/.local/opt/Grok_Bot"
    return 0
  fi
  if [[ -x /opt/Grok_Bot/grok-bot ]]; then
    printf '%s\n' /opt/Grok_Bot
    return 0
  fi
  return 1
}

detect_libva_driver() {
  [[ -n "${LIBVA_DRIVER_NAME:-}" ]] && return 0
  local card vendor device id fam
  for card in /sys/class/drm/card*/device; do
    [[ -f "$card/vendor" && -f "$card/device" ]] || continue
    vendor="$(cat "$card/vendor")"
    device="$(cat "$card/device")"
    [[ "$vendor" == "0x8086" ]] || continue
    id="${device#0x}"
    fam="${id:0:2}"
    case "$fam" in
      01|04|0a|0c|0d|0f|22)
        export LIBVA_DRIVER_NAME=i965
        return 0
        ;;
    esac
  done
}

APP_DIR="$(find_app_dir)" || {
  echo "grok-bot binary not found. Install with ./install.sh or set GROK_BOT_HOME." >&2
  exit 1
}
BIN="$APP_DIR/grok-bot"
[[ -x "$BIN" ]] || {
  echo "grok-bot binary not found at $BIN" >&2
  exit 1
}

detect_libva_driver

EXTRA=()
# Chromium sandbox needs SUID root chrome-sandbox. Docker / unprivileged
# installs fall back to --no-sandbox.
if [[ -f /.dockerenv ]] || [[ -n "${GROK_BOT_NO_SANDBOX:-}" ]]; then
  EXTRA+=(--no-sandbox)
elif [[ ! -u "$APP_DIR/chrome-sandbox" ]] || [[ "$(stat -c '%U' "$APP_DIR/chrome-sandbox" 2>/dev/null || true)" != "root" ]]; then
  EXTRA+=(--no-sandbox)
fi

export ELECTRON_OZONE_PLATFORM_HINT="${ELECTRON_OZONE_PLATFORM_HINT:-auto}"
exec "$BIN" "${EXTRA[@]}" "$@"
