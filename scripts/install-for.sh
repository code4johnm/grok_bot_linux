#!/usr/bin/env bash
# Dispatcher for other agents: Install Grok Bot for ubuntu|rocky
#
#   ./scripts/install-for.sh ubuntu [--system|--user] [--with-cli]
#   ./scripts/install-for.sh rocky  [--system|--user] [--with-cli]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

TARGET="${1:-}"
shift || true

case "$TARGET" in
  ubuntu|debian|mint|kali)
    exec "$ROOT/scripts/install-ubuntu.sh" "$@"
    ;;
  rocky|rhel|alma|almalinux)
    exec "$ROOT/scripts/install-rocky.sh" "$@"
    ;;
  auto|"")
    case "$(os_family)" in
      debian) exec "$ROOT/scripts/install-ubuntu.sh" "$@" ;;
      rhel)   exec "$ROOT/scripts/install-rocky.sh" "$@" ;;
      *)
        die "cannot auto-detect a first-class target (need Ubuntu LTS or Rocky Linux). Pass ubuntu or rocky."
        ;;
    esac
    ;;
  -h|--help)
    cat <<EOF
Usage: $0 ubuntu|rocky|auto [install flags]

  ubuntu   Ubuntu LTS x86_64 (Debian/Mint/Kali reuse)
  rocky    Rocky Linux 9/10 x86_64 (RHEL/Alma reuse)
  auto     Pick from /etc/os-release

Flags are passed through (--system, --user, --with-cli, ...).
EOF
    exit 0
    ;;
  *)
    die "unknown target: $TARGET (use ubuntu or rocky)"
    ;;
esac
