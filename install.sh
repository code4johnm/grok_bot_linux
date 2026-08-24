#!/usr/bin/env bash
# Install Grok Bot Linux: runtime deps, Electron app, launcher, desktop entry.
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

PREFIX="$HOME/.local"
WITH_DOCKER=0
SKIP_DEPS=0
SKIP_SANDBOX=0
FORCE_DOWNLOAD=0
SYSTEM=0

usage() {
  cat <<EOF
Usage: $0 [options]

  --prefix DIR       Install prefix (default: \$HOME/.local)
  --system           Install to /usr/local (needs root)
  --with-docker      Also install Docker Engine + Compose
  --skip-deps        Skip apt/dnf/pacman runtime packages
  --no-sandbox-ok    Do not try to setuid chrome-sandbox
  --download         Re-fetch the app even if a copy is already present
  -h, --help         Show this help

After install:
  grok-bot
  $ROOT/launch.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="${2:?}"; shift 2 ;;
    --system) SYSTEM=1; PREFIX=/usr/local; shift ;;
    --with-docker) WITH_DOCKER=1; shift ;;
    --skip-deps) SKIP_DEPS=1; shift ;;
    --no-sandbox-ok) SKIP_SANDBOX=1; shift ;;
    --download) FORCE_DOWNLOAD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

if [[ "$SYSTEM" -eq 1 ]]; then
  OPT_DIR="${GROK_BOT_HOME:-/opt/Grok_Bot}"
  BIN_DIR="$PREFIX/bin"
  DATA_HOME="${XDG_DATA_HOME:-/usr/local/share}"
else
  OPT_DIR="${GROK_BOT_HOME:-$PREFIX/opt/Grok_Bot}"
  BIN_DIR="$PREFIX/bin"
  DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
fi

info "Grok Bot Linux $VERSION"
info "Install prefix: $PREFIX"
info "App dir:        $OPT_DIR"

if [[ "$SKIP_DEPS" -eq 0 ]]; then
  "$ROOT/scripts/install-deps.sh"
else
  info "Skipping runtime package install"
fi

if [[ "$WITH_DOCKER" -eq 1 ]]; then
  "$ROOT/scripts/install-docker.sh"
fi

mkdir -p "$OPT_DIR" "$BIN_DIR"
if [[ "$FORCE_DOWNLOAD" -eq 1 ]]; then
  rm -rf "$ROOT/app"
fi
if [[ "$FORCE_DOWNLOAD" -eq 0 && -x "$OPT_DIR/grok-bot" && -f "$OPT_DIR/chrome_100_percent.pak" ]]; then
  info "App already present at $OPT_DIR"
else
  "$ROOT/scripts/download-app.sh" "$ROOT/app"
  info "Installing application files to $OPT_DIR"
  cp -a "$ROOT/app"/. "$OPT_DIR"/
  chmod 755 "$OPT_DIR/grok-bot" "$OPT_DIR/chrome-sandbox" 2>/dev/null || true
fi

info "Installing launcher"
install -m 0755 "$ROOT/launch.sh" "$BIN_DIR/grok-bot"
ln -sfn "$BIN_DIR/grok-bot" "$BIN_DIR/grokbot"

if [[ -f "$ROOT/share/grok-bot.png" ]]; then
  icon_src="$ROOT/share/grok-bot.png"
elif [[ -f "$OPT_DIR/grok-bot.png" ]]; then
  icon_src="$OPT_DIR/grok-bot.png"
else
  icon_src=""
fi
icon_dir="$DATA_HOME/icons/hicolor/256x256/apps"
mkdir -p "$icon_dir" "$DATA_HOME/applications"
if [[ -n "$icon_src" ]]; then
  install -m 0644 "$icon_src" "$icon_dir/grok-bot.png"
  if [[ "$(readlink -f "$icon_src")" != "$(readlink -f "$OPT_DIR/grok-bot.png" 2>/dev/null || true)" ]]; then
    install -m 0644 "$icon_src" "$OPT_DIR/grok-bot.png"
  fi
fi

desktop_out="$DATA_HOME/applications/grok-bot.desktop"
sed -e "s|@BIN@|$BIN_DIR/grok-bot|" -e "s|@ICON@|grok-bot|" \
  "$ROOT/share/grok-bot.desktop.in" > "$desktop_out"
chmod 0644 "$desktop_out"

if [[ "$SYSTEM" -eq 0 ]]; then
  desktop_copy="$HOME/Desktop/grok-bot.desktop"
  if [[ -d "$HOME/Desktop" ]]; then
    cp "$desktop_out" "$desktop_copy"
    chmod 0644 "$desktop_copy"
  fi
fi

if have update-desktop-database; then
  update-desktop-database "$DATA_HOME/applications" 2>/dev/null || true
fi
if have gtk-update-icon-cache; then
  gtk-update-icon-cache -f "$DATA_HOME/icons/hicolor" 2>/dev/null || true
fi

if [[ "$SKIP_SANDBOX" -eq 0 ]]; then
  info "Setting chrome-sandbox setuid root (needed for Chromium sandbox)"
  if sudo_cmd chown root:root "$OPT_DIR/chrome-sandbox" \
     && sudo_cmd chmod 4755 "$OPT_DIR/chrome-sandbox"; then
    info "chrome-sandbox is setuid root"
  else
    warn "Could not setuid chrome-sandbox; launcher will use --no-sandbox"
  fi
fi

va="$("$ROOT/scripts/detect-vaapi.sh" || true)"
if [[ -n "$va" ]]; then
  info "VA-API driver for this GPU: $va (launcher sets LIBVA_DRIVER_NAME)"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    warn "$BIN_DIR is not on PATH. Add this to your shell rc:"
    log "  export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac

info "Installed."
log "Run:  grok-bot"
log "Or:   $BIN_DIR/grok-bot"
log "Docker GUI (after --with-docker and a re-login):"
log "  docker compose -f $ROOT/docker/docker-compose.yml up --build"
