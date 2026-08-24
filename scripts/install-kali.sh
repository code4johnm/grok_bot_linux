#!/usr/bin/env bash
# Kali Linux x86_64 installer for Grok Bot desktop (+ optional CLI).
#
# Kali is Debian/rolling, not Ubuntu. XFCE+X11 is common. apt only.
# Does not install Kali offensive/metapackage tools.
#
# System prefix (docs): /opt/grok-bot
# Non-root fallback:    $HOME/.local/opt/grok-bot
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ;;
  aarch64|arm64)
    die "Grok Bot desktop is x86_64 only on Linux. Official CLI supports arm64: ./scripts/install-cli.sh"
    ;;
  *)
    die "unsupported architecture: $ARCH (need x86_64)"
    ;;
esac

ID="$(os_id)"
VER="$(os_version_id)"
if ! is_kali; then
  die "This helper is for Kali Linux. Detected: $ID $VER. Use ./scripts/install-ubuntu.sh or ./scripts/install-rocky.sh"
fi

SESSION="${XDG_SESSION_TYPE:-unknown}"
DESKTOP="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-unknown}}"
info "Kali Linux $VER x86_64 (Debian/rolling — not Ubuntu)"
info "Session: $SESSION  Desktop: $DESKTOP (do not assume GNOME)"
if [[ "$SESSION" == "wayland" ]]; then
  info "Wayland detected. If the GUI fails: ELECTRON_OZONE_PLATFORM_HINT=x11 grok-bot"
fi
if is_root; then
  warn "Running as root. Install system-wide, then launch grok-bot as a normal user — do not live as root."
fi

SYSTEM_REQ=0
USER_REQ=0
PASS=()
for arg in "$@"; do
  case "$arg" in
    --system) SYSTEM_REQ=1 ;;
    --user) USER_REQ=1 ;;
    *) PASS+=("$arg") ;;
  esac
done

if [[ "$SYSTEM_REQ" -eq 1 && "$USER_REQ" -eq 1 ]]; then
  die "use either --system or --user, not both"
fi

# Privileged Kali sessions: still install to /opt, not /root/.local
if [[ "$USER_REQ" -eq 0 && "$SYSTEM_REQ" -eq 0 ]] && is_root; then
  SYSTEM_REQ=1
  info "No --user given while root; using system prefix /opt/grok-bot"
fi

if [[ "$SYSTEM_REQ" -eq 1 ]]; then
  if ! is_root; then
    have sudo || die "system install to /opt/grok-bot needs sudo"
    exec sudo --preserve-env=GROK_BOT_HOME,GROK_BOT_LINUX_HOME,GROK_BOT_CACHE,GROK_BIN_DIR,XDG_SESSION_TYPE,XDG_CURRENT_DESKTOP \
      "$0" --system "${PASS[@]}"
  fi
  info "System install -> /opt/grok-bot"
  info "Grok Bot desktop: community Linux port. No Kali metapackages will be installed."
  exec "$ROOT/install.sh" --system --opt-dir /opt/grok-bot "${PASS[@]}"
fi

info "Non-root install -> \$HOME/.local/opt/grok-bot"
info "Docs prefer /opt/grok-bot: re-run with --system when sudo is available."
info "Grok Bot desktop: community Linux port. No Kali metapackages will be installed."
exec "$ROOT/install.sh" --user --opt-dir "${HOME}/.local/opt/grok-bot" "${PASS[@]}"
