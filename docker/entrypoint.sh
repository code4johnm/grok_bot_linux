#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${GROK_BOT_HOME:-/opt/Grok_Bot}"
BIN="$APP_DIR/grok-bot"

if [[ ! -x "$BIN" ]]; then
  echo "grok-bot not found at $BIN" >&2
  echo "Mount the app at /opt/Grok_Bot or rebuild the image with the bundled app." >&2
  exit 1
fi

if [[ -n "${LIBVA_DRIVER_NAME:-}" ]]; then
  :
elif [[ -x /usr/local/bin/detect-vaapi.sh ]]; then
  va="$(/usr/local/bin/detect-vaapi.sh || true)"
  [[ -n "$va" ]] && export LIBVA_DRIVER_NAME="$va"
fi

export ELECTRON_OZONE_PLATFORM_HINT="${ELECTRON_OZONE_PLATFORM_HINT:-auto}"
export GROK_BOT_NO_SANDBOX=1

# Keep Chromium on a UTF-8 locale so CJK, emoji, and symbols render.
current="${LC_ALL:-${LC_CTYPE:-${LANG:-C}}}"
case "$current" in
  *.UTF-8|*.utf8|*.UTF8|C.UTF-8|C.utf8) ;;
  *)
    export LANG=C.UTF-8 LC_ALL=C.UTF-8 LC_CTYPE=C.UTF-8
    ;;
esac

exec "$BIN" --no-sandbox "$@"
