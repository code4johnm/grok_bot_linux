#!/usr/bin/env bash
# Kali Linux x86_64 installer for Grok Bot desktop (+ optional CLI).
#
# Primary rolling Debian-family OS: Kali Linux x86_64 (apt).
# Package names come from debian-runtime-packages.sh (Ubuntu LTS names first,
# classic Debian/Kali aliases second). Same app layout as Ubuntu and Rocky.
#
# Default (non-root): $HOME/.local/opt/grok-bot
# System (sudo):      /opt/grok-bot + /usr/local/bin/grok-bot
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
info "Kali Linux $VER x86_64 (primary Debian-family rolling target)"

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

if [[ "$SYSTEM_REQ" -eq 1 ]]; then
  if ! is_root; then
    have sudo || die "system install to /opt/grok-bot needs sudo"
    exec sudo --preserve-env=GROK_BOT_HOME,GROK_BOT_LINUX_HOME,GROK_BOT_CACHE,GROK_BIN_DIR \
      "$0" --system "${PASS[@]}"
  fi
  info "System install -> /opt/grok-bot"
  info "Grok Bot desktop: community Linux port (no official vendor .deb)"
  exec "$ROOT/install.sh" --system --opt-dir /opt/grok-bot "${PASS[@]}"
fi

info "Non-root install -> \$HOME/.local/opt/grok-bot"
info "Grok Bot desktop: community Linux port (no official vendor .deb)"
exec "$ROOT/install.sh" --user --opt-dir "${HOME}/.local/opt/grok-bot" "${PASS[@]}"
