#!/usr/bin/env bash
# Dispatcher for other agents: Install Grok Bot for ubuntu|rocky|kali
#
#   ./scripts/install-for.sh ubuntu [--system|--user] [--with-cli]
#   ./scripts/install-for.sh rocky  [--system|--user] [--with-cli]
#   ./scripts/install-for.sh kali   [--system|--user] [--with-cli]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

TARGET="${1:-}"
shift || true

case "$TARGET" in
  ubuntu|debian|mint)
    exec "$ROOT/scripts/install-ubuntu.sh" "$@"
    ;;
  rocky|rhel|alma|almalinux)
    exec "$ROOT/scripts/install-rocky.sh" "$@"
    ;;
  kali)
    exec "$ROOT/scripts/install-kali.sh" "$@"
    ;;
  auto|"")
    if is_kali; then
      exec "$ROOT/scripts/install-kali.sh" "$@"
    fi
    case "$(os_family)" in
      debian) exec "$ROOT/scripts/install-ubuntu.sh" "$@" ;;
      rhel)   exec "$ROOT/scripts/install-rocky.sh" "$@" ;;
      *)
        die "cannot auto-detect a first-class target (need Ubuntu LTS, Rocky Linux, or Kali). Pass ubuntu, rocky, or kali."
        ;;
    esac
    ;;
  -h|--help)
    cat <<EOF
Usage: $0 ubuntu|rocky|kali|auto [install flags]

  ubuntu   Ubuntu LTS x86_64 (Debian/Mint reuse)
  rocky    Rocky Linux 9/10 x86_64 (RHEL/Alma reuse)
  kali     Kali Linux x86_64 (rolling Debian-family)
  auto     Pick from /etc/os-release

System prefix on every dist: /opt/grok-bot

Flags are passed through (--system, --user, --with-cli, ...).
EOF
    exit 0
    ;;
  *)
    die "unknown target: $TARGET (use ubuntu, rocky, or kali)"
    ;;
esac
