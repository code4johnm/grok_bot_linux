#!/usr/bin/env bash
# Ubuntu LTS x86_64 installer for Grok Bot desktop (+ optional CLI).
#
# Primary OS: Ubuntu 24.04 / 26.04 LTS, x86_64
# Reuse:      Debian, Linux Mint, Kali — same script; package names that
#             differ (t64 vs classic) are resolved in debian-runtime-packages.sh
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

FAMILY="$(os_family)"
ID="$(os_id)"
VER="$(os_version_id)"
if [[ "$FAMILY" != "debian" ]]; then
  die "Primary target is Ubuntu LTS x86_64. This helper is Debian-compatible (Debian, Mint, Kali). Detected: $ID. Use ./install.sh on other families."
fi
if is_ubuntu_lts; then
  info "Ubuntu LTS $VER x86_64 (primary target)"
elif [[ "$ID" == "ubuntu" ]]; then
  warn "Ubuntu $VER is not a listed LTS (22.04/24.04/26.04). Continuing with Ubuntu package names."
else
  warn "Not Ubuntu LTS ($ID $VER). Reusing the Ubuntu installer; dependency names are tweaked automatically (t64 vs classic)."
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
  info "System install -> /opt/grok-bot"
  info "Grok Bot desktop: community Linux port (no official vendor .deb)"
  exec "$ROOT/install.sh" --system --opt-dir /opt/grok-bot "${PASS[@]}"
fi

info "Non-root install -> \$HOME/.local/opt/grok-bot"
info "Grok Bot desktop: community Linux port (no official vendor .deb)"
exec "$ROOT/install.sh" --user --opt-dir "${HOME}/.local/opt/grok-bot" "${PASS[@]}"
