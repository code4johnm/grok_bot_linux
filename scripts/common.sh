#!/usr/bin/env bash
# Shared helpers. Source after ROOT is set, or from scripts/.
set -euo pipefail

if [[ -z "${ROOT:-}" ]]; then
  _COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ROOT="$(cd "$_COMMON_DIR/.." && pwd)"
fi

VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || echo 0.24.0)"
APP_NAME="Grok Bot"
APP_ID="grok-bot"
DEFAULT_OPT_DIR="${GROK_BOT_HOME:-$HOME/.local/opt/Grok_Bot}"

UPSTREAM_TAG="v${VERSION}"
UPSTREAM_TARBALL="Grok_Bot_${VERSION}_linux_x64.tar.gz"
UPSTREAM_URL="https://github.com/Nichokas/grokbot-linux-port/releases/download/${UPSTREAM_TAG}/${UPSTREAM_TARBALL}"
UPSTREAM_SHA256="f6b6495f9398a9d60702a282b404ac52e2b1c1c345d3ba81bbbd242e49ea6aad"

log()  { printf '%s\n' "$*"; }
info() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

is_root() { [[ "$(id -u)" -eq 0 ]]; }

sudo_cmd() {
  if is_root; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    die "need root or sudo for: $*"
  fi
}

os_family() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID_LIKE:-$ID}" in
      *debian*|*ubuntu*|*linuxmint*|kali) echo debian ;;
      *rhel*|*fedora*|*centos*)           echo fedora ;;
      *arch*|arch)                        echo arch ;;
      *)
        case "$ID" in
          debian|ubuntu|kali|linuxmint) echo debian ;;
          fedora|rhel|centos|rocky|almalinux) echo fedora ;;
          arch|manjaro|endeavouros) echo arch ;;
          *) echo unknown ;;
        esac
        ;;
    esac
  else
    echo unknown
  fi
}
