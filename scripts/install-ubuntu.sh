#!/usr/bin/env bash
# Ubuntu LTS / Debian-family installer for Grok Bot desktop (+ optional CLI).
#
# Default (non-root): $HOME/.local/opt/grok-bot
# System (sudo):      /opt/grok-bot + /usr/local/bin/grok-bot
#
# Desktop port is x86_64 only. Official CLI also supports aarch64.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ;;
  aarch64|arm64)
    die "Grok Bot desktop Linux port is x86_64 only. Official CLI supports arm64: ./scripts/install-cli.sh"
    ;;
  *)
    die "unsupported architecture: $ARCH (need x86_64)"
    ;;
esac

FAMILY="$(os_family)"
if [[ "$FAMILY" != "debian" ]]; then
  warn "This helper targets Ubuntu LTS and Debian-family systems (Mint, Kali)."
  warn "Detected family: $FAMILY — continuing with generic install.sh"
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

if [[ "$SYSTEM_REQ" -eq 1 ]]; then
  if ! is_root; then
    have sudo || die "system install to /opt/grok-bot needs sudo"
    exec sudo --preserve-env=GROK_BOT_HOME,GROK_BOT_LINUX_HOME,GROK_BOT_CACHE,GROK_BIN_DIR \
      "$0" --system "${PASS[@]}"
  fi
  info "Ubuntu/Debian system install -> /opt/grok-bot"
  info "Grok Bot desktop: community Linux port (no official vendor .deb)"
  exec "$ROOT/install.sh" --system --opt-dir /opt/grok-bot "${PASS[@]}"
fi

info "Non-root install -> \$HOME/.local/opt/grok-bot"
info "Grok Bot desktop: community Linux port (no official vendor .deb)"
exec "$ROOT/install.sh" --user --opt-dir "${HOME}/.local/opt/grok-bot" "${PASS[@]}"
