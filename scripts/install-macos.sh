#!/usr/bin/env bash
# Official Grok Bot for macOS (Apple Silicon + Intel). Not a Linux DMG wrapper.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

DOWNLOAD_ONLY=0
OPEN_DMG=0
USE_BREW=0
WITH_CLI=0
REQ_VERSION=""
REQ_ARCH=""
DEST=""

usage() {
  cat <<EOF
Usage: $0 [options]

Install or download the official Grok Bot macOS app (product name sand).

  --arch arm64|x64   CPU (default: this machine, else arm64)
  --version X        Pin a desktop version (default: Cursor update API)
  --download-only    Fetch the .dmg; do not copy into /Applications
  --open             Open the .dmg after download (macOS Finder)
  --brew             Prefer Homebrew cask grok-bot on macOS
  --dest DIR         Where to save the .dmg (default: cache)
  --with-cli         Also install the official Grok CLI
  -h, --help         Show this help

On Linux this script only downloads the official .dmg.
On macOS it mounts the disk image and copies Grok Bot.app to /Applications
unless --download-only is set.

  brew install --cask grok-bot
  open -a "Grok Bot"
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) REQ_ARCH="${2:?}"; shift 2 ;;
    --version) REQ_VERSION="${2:?}"; shift 2 ;;
    --download-only) DOWNLOAD_ONLY=1; shift ;;
    --open) OPEN_DMG=1; shift ;;
    --brew) USE_BREW=1; shift ;;
    --dest) DEST="${2:?}"; shift 2 ;;
    --with-cli) WITH_CLI=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

OS="$(host_os)"
CPU="${REQ_ARCH:-}"
if [[ -z "$CPU" ]]; then
  if [[ "$OS" == "macos" ]]; then
    CPU="$(official_cpu)"
  else
    CPU="arm64"
  fi
fi
case "$CPU" in
  arm64|aarch64) CPU=arm64 ;;
  x64|x86_64|amd64|intel) CPU=x64 ;;
  *) die "unsupported macOS arch: $CPU (use arm64 or x64)" ;;
esac

if [[ "$USE_BREW" -eq 1 ]]; then
  [[ "$OS" == "macos" ]] || die "--brew requires macOS"
  have brew || die "Homebrew not found"
  info "Installing grok-bot cask via Homebrew"
  brew install --cask grok-bot
  if [[ "$WITH_CLI" -eq 1 ]]; then
    "$ROOT/scripts/install-cli.sh"
  fi
  info "Installed. Run: open -a \"Grok Bot\""
  exit 0
fi

VER="${REQ_VERSION:-}"
URL=""
if [[ -z "$VER" ]]; then
  rel="$(latest_official_release macos "$CPU" || true)"
  if [[ -n "$rel" ]]; then
    VER="${rel%%$'\t'*}"
  else
    VER="$OFFICIAL_PINNED_VERSION"
    warn "update API unavailable; pinning $VER"
  fi
fi
VER="$(ver_norm "$VER")"
URL="$(official_named_url macos "$CPU" "$VER")" || die "no named macOS URL for $CPU"

CACHE="${GROK_BOT_CACHE:-$CACHE_DIR}"
DEST="${DEST:-$CACHE/official}"
mkdir -p "$DEST"
artifact="$(official_artifact_name macos "$CPU" "$VER")"
path="$DEST/$artifact"

info "Official Grok Bot macOS $VER ($CPU)"
info "Downloading $URL"
http_download "$URL" "$path"
info "Saved $path"

if [[ "$OPEN_DMG" -eq 1 ]]; then
  if [[ "$OS" == "macos" ]] && have open; then
    open "$path"
  elif have xdg-open; then
    xdg-open "$path" >/dev/null 2>&1 || true
  else
    warn "cannot open $path on this OS"
  fi
fi

if [[ "$OS" != "macos" || "$DOWNLOAD_ONLY" -eq 1 ]]; then
  log "Install on a Mac:"
  log "  open \"$path\""
  log "  drag Grok Bot.app to /Applications"
  log "  or: brew install --cask grok-bot"
  if [[ "$WITH_CLI" -eq 1 ]]; then
    "$ROOT/scripts/install-cli.sh"
  fi
  exit 0
fi

have hdiutil || die "hdiutil not found"
MOUNT="$(mktemp -d "${TMPDIR:-/tmp}/grok-bot-dmg.XXXXXX")"
cleanup() { hdiutil detach "$MOUNT" >/dev/null 2>&1 || true; rmdir "$MOUNT" 2>/dev/null || true; }
trap cleanup EXIT
info "Mounting $path"
hdiutil attach -nobrowse -quiet -mountpoint "$MOUNT" "$path"
APP="$(find "$MOUNT" -maxdepth 2 -name '*.app' -type d -print -quit)"
[[ -n "$APP" ]] || die "disk image did not contain Grok Bot.app"
TARGET="/Applications/$(basename "$APP")"
info "Installing $(basename "$APP") -> $TARGET"
rm -rf "$TARGET"
cp -R "$APP" "$TARGET"
cleanup
trap - EXIT
info "Installed. Run: open -a \"Grok Bot\""

if [[ "$WITH_CLI" -eq 1 ]]; then
  "$ROOT/scripts/install-cli.sh"
fi
