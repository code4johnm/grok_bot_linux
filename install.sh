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
NO_AUTO_UPDATE=0
WITH_CLI=0
OPT_DIR_OVERRIDE=""

usage() {
  cat <<EOF
Usage: $0 [options]

  --prefix DIR       Install prefix (default: \$HOME/.local)
  --system           Install to /usr/local + /opt/grok-bot (needs root)
  --opt-dir DIR      Application directory (default: \$HOME/.local/opt/grok-bot
                     or /opt/grok-bot with --system)
  --user             Force a non-root prefix install (default)
  --with-cli         Also install the official Grok CLI (\$HOME/.grok/bin)
  --with-docker      Also install Docker Engine + Compose
  --skip-deps        Skip apt/dnf/pacman runtime packages
  --no-sandbox-ok    Do not try to setuid chrome-sandbox
  --download         Re-fetch the app even if a copy is already present
  --no-auto-update   Do not install the daily systemd update timer
  -h, --help         Show this help

After install:
  grok-bot
  grok --version     (if --with-cli)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="${2:?}"; shift 2 ;;
    --system) SYSTEM=1; PREFIX=/usr/local; shift ;;
    --user) SYSTEM=0; PREFIX="$HOME/.local"; shift ;;
    --opt-dir) OPT_DIR_OVERRIDE="${2:?}"; shift 2 ;;
    --with-cli) WITH_CLI=1; shift ;;
    --with-docker) WITH_DOCKER=1; shift ;;
    --skip-deps) SKIP_DEPS=1; shift ;;
    --no-sandbox-ok) SKIP_SANDBOX=1; shift ;;
    --download) FORCE_DOWNLOAD=1; shift ;;
    --no-auto-update) NO_AUTO_UPDATE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

if [[ "$SYSTEM" -eq 1 ]]; then
  OPT_DIR="${GROK_BOT_HOME:-/opt/grok-bot}"
  BIN_DIR="$PREFIX/bin"
  DATA_HOME="${XDG_DATA_HOME:-/usr/share}"
  PACKAGING_DIR="${GROK_BOT_LINUX_HOME:-/usr/local/lib/grok-bot-linux}"
else
  OPT_DIR="${GROK_BOT_HOME:-$PREFIX/opt/grok-bot}"
  BIN_DIR="$PREFIX/bin"
  DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
  PACKAGING_DIR="${GROK_BOT_LINUX_HOME:-$PREFIX/opt/grok_bot_linux}"
fi
[[ -n "$OPT_DIR_OVERRIDE" ]] && OPT_DIR="$OPT_DIR_OVERRIDE"

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

info "Installing packaging files to $PACKAGING_DIR"
if [[ "$(readlink -f "$ROOT")" != "$(readlink -f "$PACKAGING_DIR")" ]]; then
  mkdir -p "$PACKAGING_DIR"
  for item in install.sh uninstall.sh launch.sh VERSION Makefile README.md LICENSE scripts share docker; do
    if [[ -e "$ROOT/$item" ]]; then
      rm -rf "$PACKAGING_DIR/$item"
      cp -a "$ROOT/$item" "$PACKAGING_DIR/$item"
    fi
  done
fi
chmod 0755 "$PACKAGING_DIR/install.sh" "$PACKAGING_DIR/uninstall.sh" "$PACKAGING_DIR/launch.sh" \
  "$PACKAGING_DIR/scripts/"*.sh 2>/dev/null || true
cat > "$PACKAGING_DIR/install.conf" <<EOF
PREFIX="$PREFIX"
OPT_DIR="$OPT_DIR"
BIN_DIR="$BIN_DIR"
DATA_HOME="$DATA_HOME"
SYSTEM="$SYSTEM"
PACKAGING_DIR="$PACKAGING_DIR"
GROK_BOT_LINUX_REPO="${WRAPPER_REPO:-}"
EOF
if git -C "$ROOT" rev-parse HEAD >/dev/null 2>&1; then
  git -C "$ROOT" rev-parse HEAD > "$PACKAGING_DIR/.wrapper-revision"
fi
printf '%s\n' "$VERSION" > "$OPT_DIR/GROK_BOT_VERSION"

info "Installing launcher"
mkdir -p "$BIN_DIR"
sed -e "s|@PACKAGING@|$PACKAGING_DIR|" "$ROOT/share/grok-bot-wrapper.in" > "$BIN_DIR/grok-bot"
chmod 0755 "$BIN_DIR/grok-bot"
ln -sfn "$BIN_DIR/grok-bot" "$BIN_DIR/grokbot"

if [[ -f "$ROOT/share/grok-bot.png" ]]; then
  icon_src="$ROOT/share/grok-bot.png"
elif [[ -f "$OPT_DIR/grok-bot.png" ]]; then
  icon_src="$OPT_DIR/grok-bot.png"
else
  icon_src=""
fi
mkdir -p "$DATA_HOME/applications"
if [[ -n "$icon_src" ]]; then
  for icon_size in 512 256; do
    icon_dir="$DATA_HOME/icons/hicolor/${icon_size}x${icon_size}/apps"
    mkdir -p "$icon_dir"
    install -m 0644 "$icon_src" "$icon_dir/grok-bot.png"
  done
  if [[ "$(readlink -f "$icon_src")" != "$(readlink -f "$OPT_DIR/grok-bot.png" 2>/dev/null || true)" ]]; then
    install -m 0644 "$icon_src" "$OPT_DIR/grok-bot.png"
  fi
  install -m 0644 "$icon_src" "$OPT_DIR/icon.png"
fi

if [[ "$SYSTEM" -eq 1 ]]; then
  desktop_icon="$OPT_DIR/icon.png"
else
  desktop_icon="grok-bot"
fi
desktop_out="$DATA_HOME/applications/grok-bot.desktop"
sed -e "s|@BIN@|$BIN_DIR/grok-bot|" -e "s|@ICON@|$desktop_icon|" \
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
    printf 'suid\n' > "$OPT_DIR/.sandbox-attempt" 2>/dev/null || true
  else
    warn "Could not setuid chrome-sandbox; launcher will use --no-sandbox"
    printf 'no-sandbox\n' > "$OPT_DIR/.sandbox-attempt" 2>/dev/null || true
  fi
fi

selinux_restore_app "$OPT_DIR"

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

if [[ "$NO_AUTO_UPDATE" -eq 0 ]] && have systemctl; then
  if [[ "$SYSTEM" -eq 0 ]]; then
    unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    mkdir -p "$unit_dir"
    sed -e "s|@PACKAGING@|$PACKAGING_DIR|" \
      "$ROOT/share/grok-bot-update.service.in" > "$unit_dir/grok-bot-update.service"
    install -m 0644 "$ROOT/share/grok-bot-update.timer.in" "$unit_dir/grok-bot-update.timer"
    if systemctl --user daemon-reload >/dev/null 2>&1 \
       && systemctl --user enable --now grok-bot-update.timer >/dev/null 2>&1; then
      info "Daily auto-update timer enabled (systemd --user)"
    else
      warn "Could not enable systemd user timer; run: grok-bot update"
    fi
  elif is_root; then
    sed -e "s|@PACKAGING@|$PACKAGING_DIR|" \
      "$ROOT/share/grok-bot-update.service.in" > /etc/systemd/system/grok-bot-update.service
    install -m 0644 "$ROOT/share/grok-bot-update.timer.in" /etc/systemd/system/grok-bot-update.timer
    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable --now grok-bot-update.timer >/dev/null 2>&1 || \
      warn "Could not enable system update timer"
  fi
fi

if [[ "$WITH_CLI" -eq 1 ]]; then
  if [[ "$SYSTEM" -eq 1 ]]; then
    "$ROOT/scripts/install-cli.sh" --system-profile
  else
    "$ROOT/scripts/install-cli.sh"
  fi
fi

info "Installed."
log "Run:     grok-bot"
log "Update:  grok-bot update"
log "Check:   grok-bot update --check"
[[ "$WITH_CLI" -eq 1 ]] && log "CLI:     grok --version"
log "Docker GUI (after --with-docker and a re-login):"
log "  docker compose -f $ROOT/docker/docker-compose.yml up --build"
