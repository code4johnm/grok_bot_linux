#!/usr/bin/env bash
# Populate ROOT/app with the Grok Bot Electron tree.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

DEST="${1:-$ROOT/app}"
CACHE="${GROK_BOT_CACHE:-$ROOT/.cache}"
mkdir -p "$CACHE" "$DEST"

if [[ -x "$DEST/grok-bot" && -f "$DEST/chrome_100_percent.pak" ]]; then
  info "App already present at $DEST"
  exit 0
fi

if [[ -x "$DEFAULT_OPT_DIR/grok-bot" && -f "$DEFAULT_OPT_DIR/chrome_100_percent.pak" ]]; then
  info "Copying installed app from $DEFAULT_OPT_DIR"
  mkdir -p "$DEST"
  cp -a "$DEFAULT_OPT_DIR"/. "$DEST"/
  chmod 755 "$DEST/chrome-sandbox" 2>/dev/null || true
  exit 0
fi

archive="$CACHE/$UPSTREAM_TARBALL"
info "Downloading $UPSTREAM_URL"
if have curl; then
  curl -fL --retry 3 --retry-delay 2 -o "$archive" "$UPSTREAM_URL"
elif have wget; then
  wget -O "$archive" "$UPSTREAM_URL"
else
  die "need curl or wget to download $UPSTREAM_TARBALL"
fi

if have sha256sum; then
  got="$(sha256sum "$archive" | awk '{print $1}')"
  if [[ "$got" != "$UPSTREAM_SHA256" ]]; then
    rm -f "$archive"
    die "checksum mismatch for $UPSTREAM_TARBALL (got $got)"
  fi
else
  warn "sha256sum not found; skipping checksum"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -xzf "$archive" -C "$tmp"
inner="$(find "$tmp" -maxdepth 2 -type f -name grok-bot -executable | head -n1)"
[[ -n "$inner" ]] || die "downloaded archive did not contain grok-bot"
src="$(dirname "$inner")"
mkdir -p "$DEST"
cp -a "$src"/. "$DEST"/
chmod 755 "$DEST/chrome-sandbox" 2>/dev/null || true
info "App extracted to $DEST"
