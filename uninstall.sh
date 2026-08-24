#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

PREFIX="${1:-$HOME/.local}"
OPT_DIR="${GROK_BOT_HOME:-$PREFIX/opt/grok-bot}"
BIN_DIR="$PREFIX/bin"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PACKAGING_DIR="${GROK_BOT_LINUX_HOME:-$PREFIX/opt/grok_bot_linux}"
if [[ -f "$PACKAGING_DIR/install.conf" ]]; then
  # shellcheck disable=SC1091
  source "$PACKAGING_DIR/install.conf"
elif [[ -f /usr/lib/grok-bot-linux/install.conf ]]; then
  # shellcheck disable=SC1091
  source /usr/lib/grok-bot-linux/install.conf
fi

info "Removing $OPT_DIR"
rm -rf "$OPT_DIR" "$OPT_DIR.next" "$OPT_DIR.prev"
# Previous layout names
[[ "$OPT_DIR" != "${HOME}/.local/opt/Grok_Bot" ]] && rm -rf "${HOME}/.local/opt/Grok_Bot" 2>/dev/null || true

if have systemctl; then
  systemctl --user disable --now grok-bot-update.timer >/dev/null 2>&1 || true
  rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/grok-bot-update."{service,timer}
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  if is_root; then
    systemctl disable --now grok-bot-update.timer >/dev/null 2>&1 || true
    rm -f /etc/systemd/system/grok-bot-update.{service,timer}
    systemctl daemon-reload >/dev/null 2>&1 || true
  fi
fi

if [[ "$(readlink -f "$PACKAGING_DIR")" != "$(readlink -f "$ROOT")" ]]; then
  info "Removing $PACKAGING_DIR"
  rm -rf "$PACKAGING_DIR"
fi

rm -f "$BIN_DIR/grok-bot" "$BIN_DIR/grokbot"
rm -f "$DATA_HOME/applications/grok-bot.desktop"
rm -f "$HOME/Desktop/grok-bot.desktop"
rm -f "$DATA_HOME/icons/hicolor/"{512x512,256x256,128x128,64x64,48x48,32x32}/apps/grok-bot.png

if [[ "${SYSTEM:-0}" -eq 1 ]]; then
  rm -f /usr/local/bin/grok-bot /usr/local/bin/grokbot /usr/bin/grok-bot 2>/dev/null || true
  rm -f /usr/share/applications/grok-bot.desktop \
        /usr/local/share/applications/grok-bot.desktop 2>/dev/null || true
  rm -f /usr/share/icons/hicolor/256x256/apps/grok-bot.png 2>/dev/null || true
  rm -rf /usr/lib/grok-bot-linux /usr/local/lib/grok-bot-linux 2>/dev/null || true
fi

info "Uninstalled application files."
log "User data left in place: ~/.grokbot  ~/.config/Grok Bot  ~/.cache/grok-bot"
log "Remove those directories yourself if you want a clean slate."
