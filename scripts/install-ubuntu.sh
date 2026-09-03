#!/usr/bin/env bash
# Ubuntu LTS installer for Grok Bot desktop (+ optional CLI).
#
# Primary OS: Ubuntu 24.04 / 26.04 LTS, x86_64 or aarch64
# Reuse:      Debian, Linux Mint — same script; package names that
#             differ (t64 vs classic) are resolved in debian-runtime-packages.sh
#
# Default (non-root): $HOME/.local/opt/grok-bot
# System (sudo):      /opt/grok-bot + /usr/local/bin/grok-bot
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

require_desktop_arch
ARCH="$(uname -m)"

FAMILY="$(os_family)"
ID="$(os_id)"
VER="$(os_version_id)"
if is_kali; then
  die "Kali Linux is a first-class target. Use ./scripts/install-kali.sh"
fi
if [[ "$FAMILY" != "debian" ]]; then
  die "This helper is for Ubuntu LTS (Debian/Mint reuse). Detected: $ID. Use ./scripts/install-rocky.sh or ./scripts/install-kali.sh"
fi
if is_ubuntu_lts; then
  info "Ubuntu LTS $VER $ARCH (primary desktop target)"
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
  info "Grok Bot desktop: official Linux payload (community tarball of the vendor .deb)"
  exec "$ROOT/install.sh" --system --opt-dir /opt/grok-bot "${PASS[@]}"
fi

info "Non-root install -> \$HOME/.local/opt/grok-bot"
info "Grok Bot desktop: official Linux payload (community tarball of the vendor .deb)"
exec "$ROOT/install.sh" --user --opt-dir "${HOME}/.local/opt/grok-bot" "${PASS[@]}"
