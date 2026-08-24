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
  if [[ -f "$ROOT/install.conf" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/install.conf"
    if [[ -n "${OPT_DIR:-}" && -x "${OPT_DIR}/grok-bot" ]]; then
      printf '%s\n' "$OPT_DIR"
      return 0
    fi
  fi
  if [[ -x "${HOME}/.local/opt/grok-bot/grok-bot" ]]; then
    printf '%s\n' "${HOME}/.local/opt/grok-bot"
    return 0
  fi
  if [[ -x "${HOME}/.local/opt/Grok_Bot/grok-bot" ]]; then
    printf '%s\n' "${HOME}/.local/opt/Grok_Bot"
    return 0
  fi
  if [[ -x /opt/grok-bot/grok-bot ]]; then
    printf '%s\n' /opt/grok-bot
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

linux_help() {
  cat <<EOF
Grok Bot Linux launcher

  grok-bot                 Start Grok Bot
  grok-bot update          Update this package, Grok Bot, and runtime deps
  grok-bot update --check  Show available updates
  grok-bot --version       Print installed versions

Extra arguments are passed to the Electron app.

Disable automatic updates with GROK_BOT_NO_AUTO_UPDATE=1.
EOF
}

run_update() {
  local updater=""
  if [[ -x "$ROOT/scripts/update.sh" ]]; then
    updater="$ROOT/scripts/update.sh"
  elif [[ -x "${HOME}/.local/opt/grok_bot_linux/scripts/update.sh" ]]; then
    updater="${HOME}/.local/opt/grok_bot_linux/scripts/update.sh"
  elif [[ -x /usr/lib/grok-bot-linux/scripts/update.sh ]]; then
    updater=/usr/lib/grok-bot-linux/scripts/update.sh
  elif [[ -x /usr/local/lib/grok-bot-linux/scripts/update.sh ]]; then
    updater=/usr/local/lib/grok-bot-linux/scripts/update.sh
  elif [[ -x /usr/local/opt/grok_bot_linux/scripts/update.sh ]]; then
    updater=/usr/local/opt/grok_bot_linux/scripts/update.sh
  else
    echo "update script not found. Re-run install.sh from the grok_bot_linux tree." >&2
    exit 1
  fi
  exec "$updater" "$@"
}

print_versions() {
  # shellcheck source=scripts/common.sh
  if [[ -f "$ROOT/scripts/common.sh" ]]; then
    # shellcheck disable=SC1091
    source "$ROOT/scripts/common.sh"
  fi
  local app_dir app_ver wrap
  app_dir="$(find_app_dir 2>/dev/null || true)"
  app_ver="unknown"
  if [[ -n "${app_dir:-}" && -f "$app_dir/GROK_BOT_VERSION" ]]; then
    app_ver="$(tr -d '[:space:]' < "$app_dir/GROK_BOT_VERSION")"
  elif [[ -f "$ROOT/VERSION" ]]; then
    app_ver="$(tr -d '[:space:]' < "$ROOT/VERSION")"
  fi
  wrap="unknown"
  if [[ -f "$ROOT/.wrapper-revision" ]]; then
    wrap="$(tr -d '[:space:]' < "$ROOT/.wrapper-revision")"
  elif command -v git >/dev/null && git -C "$ROOT" rev-parse HEAD >/dev/null 2>&1; then
    wrap="$(git -C "$ROOT" rev-parse --short HEAD)"
  fi
  echo "Grok Bot        $app_ver"
  echo "grok_bot_linux  ${wrap:0:12}"
}

case "${1:-}" in
  update|--update)
    shift
    run_update "$@"
    ;;
  --linux-help)
    linux_help
    exit 0
    ;;
  --version)
    print_versions
    exit 0
    ;;
esac

apply_staged_update() {
  local app_dir="$1"
  local next="${app_dir}.next"
  [[ -x "$next/grok-bot" && -f "$next/chrome_100_percent.pak" ]] || return 0
  echo "==> applying staged Grok Bot update" >&2
  rm -rf "${app_dir}.prev"
  mv "$app_dir" "${app_dir}.prev"
  mv "$next" "$app_dir"
  if [[ -f "$ROOT/share/grok-bot.png" ]]; then
    cp -f "$ROOT/share/grok-bot.png" "$app_dir/grok-bot.png"
  fi
  rm -rf "${app_dir}.prev"
}

maybe_auto_update() {
  [[ -z "${GROK_BOT_NO_AUTO_UPDATE:-}" ]] || return 0
  [[ ! -f /.dockerenv ]] || return 0
  [[ -x "$ROOT/scripts/update.sh" ]] || return 0
  local cache="${GROK_BOT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/grok-bot}"
  mkdir -p "$cache"
  local stamp="$cache/last-update-check"
  local now last
  now="$(date +%s)"
  if [[ -f "$stamp" ]]; then
    last="$(tr -d '[:space:]' < "$stamp" || true)"
    if [[ "$last" =~ ^[0-9]+$ ]] && (( now - last < 86400 )); then
      return 0
    fi
  fi
  printf '%s\n' "$now" > "$stamp"
  nohup "$ROOT/scripts/update.sh" --auto --notify >/dev/null 2>&1 &
  disown >/dev/null 2>&1 || true
}

APP_DIR="$(find_app_dir)" || {
  echo "grok-bot binary not found. Install with ./install.sh or set GROK_BOT_HOME." >&2
  exit 1
}

apply_staged_update "$APP_DIR" || true
maybe_auto_update || true

BIN="$APP_DIR/grok-bot"
[[ -x "$BIN" ]] || {
  echo "grok-bot binary not found at $BIN" >&2
  exit 1
}

# Chromium/Electron need a UTF-8 locale or CJK, emoji, and symbols render as
# tofu or "?" and clipboard/input mangle non-ASCII.
ensure_utf8_locale() {
  local current="${LC_ALL:-${LC_CTYPE:-${LANG:-C}}}"
  case "$current" in
    *.UTF-8|*.utf8|*.UTF8|C.UTF-8|C.utf8) return 0 ;;
  esac
  local utf8=C.UTF-8
  if command -v locale >/dev/null 2>&1; then
    if locale -a 2>/dev/null | grep -qiE '^C\.(utf-?8)$'; then
      utf8=C.UTF-8
    elif locale -a 2>/dev/null | grep -qiE '^en_US\.(utf-?8)$'; then
      utf8=en_US.UTF-8
    fi
  fi
  export LANG="$utf8" LC_ALL="$utf8" LC_CTYPE="$utf8"
}

detect_libva_driver
ensure_utf8_locale

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
