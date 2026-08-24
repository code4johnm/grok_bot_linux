#!/usr/bin/env bash
# Rocky Linux 9/10 x86_64 installer for Grok Bot desktop (+ optional CLI).
#
# Primary enterprise OS: Rocky Linux 9 or 10, x86_64 (dnf, SELinux).
# Cousins: RHEL, AlmaLinux — same script. Fedora is not this path.
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
if [[ "$FAMILY" != "rhel" ]]; then
  die "This helper is for Rocky Linux / RHEL / AlmaLinux. Detected: $ID ($FAMILY). For Ubuntu LTS use ./scripts/install-ubuntu.sh"
fi
if is_rocky_supported; then
  info "Rocky Linux $VER x86_64 (primary enterprise target)"
elif is_rocky; then
  warn "Rocky Linux $VER is outside 9/10; continuing with Rocky package names"
elif is_rhel_family; then
  warn "Not Rocky ($ID $VER). Reusing the Rocky installer for this RHEL-family system"
fi

if ! have dnf; then
  die "dnf is required on Rocky/RHEL (not apt)"
fi

info "SELinux mode: $(selinux_mode)"
if [[ "$(selinux_mode)" == "enforcing" ]]; then
  info "Will restorecon /opt/grok-bot after install. Will not disable SELinux."
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
  info "Grok Bot desktop: community Linux port (no official vendor .rpm)"
  exec "$ROOT/install.sh" --system --opt-dir /opt/grok-bot "${PASS[@]}"
fi

info "Non-root install -> \$HOME/.local/opt/grok-bot"
info "Grok Bot desktop: community Linux port (no official vendor .rpm)"
exec "$ROOT/install.sh" --user --opt-dir "${HOME}/.local/opt/grok-bot" "${PASS[@]}"
