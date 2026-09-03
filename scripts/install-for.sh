#!/usr/bin/env bash
# Dispatcher: Install Grok Bot for ubuntu|rocky|kali
# Detection (auto): /etc/os-release
#   1. ID=kali or ID_LIKE contains kali → install-kali.sh
#   2. ID=ubuntu|debian|linuxmint (and not kali) → install-ubuntu.sh
#   3. ID=rocky or ID_LIKE contains rhel/centos → install-rocky.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

TARGET="${1:-}"
shift || true

# TUI-only: no Electron. Safe on 32-bit ARM. Do not dispatch to desktop installers.
if [[ "$TARGET" == "--tui-only" ]]; then
  exec "$ROOT/scripts/install-tui.sh"
fi
for _arg in "$@"; do
  if [[ "$_arg" == "--tui-only" ]]; then
    exec "$ROOT/scripts/install-tui.sh"
  fi
done

detect_target() {
  local id like
  id="$(os_id)"
  like=" $(os_id_like) "
  if [[ "$id" == "kali" || "$like" == *" kali "* ]]; then
    echo kali
    return
  fi
  case "$id" in
    ubuntu|debian|linuxmint)
      echo ubuntu
      return
      ;;
    rocky|almalinux|rhel|centos)
      echo rocky
      return
      ;;
  esac
  if [[ "$like" == *" rhel "* || "$like" == *" centos "* ]]; then
    echo rocky
    return
  fi
  if [[ "$like" == *" ubuntu "* || "$like" == *" debian "* ]]; then
    echo ubuntu
    return
  fi
  echo unknown
}

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
    case "$(detect_target)" in
      kali)   exec "$ROOT/scripts/install-kali.sh" "$@" ;;
      ubuntu) exec "$ROOT/scripts/install-ubuntu.sh" "$@" ;;
      rocky)  exec "$ROOT/scripts/install-rocky.sh" "$@" ;;
      *)
        die "cannot auto-detect a first-class target from /etc/os-release. Pass ubuntu, rocky, or kali."
        ;;
    esac
    ;;
  -h|--help)
    cat <<EOF
Usage: $0 ubuntu|rocky|kali|auto [install flags]

  ubuntu   Ubuntu LTS x86_64/aarch64 (Debian/Mint reuse)
  rocky    Rocky Linux 9/10 x86_64/aarch64 (RHEL/Alma reuse)
  kali     Kali Linux x86_64/aarch64 (Debian/rolling, not Ubuntu)
  auto     /etc/os-release: kali, then ubuntu/debian/mint, then rocky/rhel

System prefix on every dist: /opt/grok-bot

Flags are passed through (--system, --user, --with-cli, ...).

  --tui-only   Install grok-bot-tui only (no Electron). Safe on 32-bit ARM.
               Same as scripts/install-tui.sh
EOF
    exit 0
    ;;
  *)
    die "unknown target: $TARGET (use ubuntu, rocky, or kali)"
    ;;
esac
