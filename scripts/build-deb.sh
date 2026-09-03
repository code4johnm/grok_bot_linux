#!/usr/bin/env bash
# Build a .deb for Ubuntu LTS / Debian-family (amd64 or arm64).
# Layout: /opt/grok-bot, /usr/bin/grok-bot, /usr/share/applications
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

have dpkg-deb || die "dpkg-deb is required to build a .deb"

"$ROOT/scripts/download-app.sh" "$ROOT/app"
[[ -x "$ROOT/app/grok-bot" ]] || die "app payload missing"

pkg_name="grok-bot"
pkg_ver="$VERSION"
case "${UPSTREAM_ARCH:-$(linux_cpu)}" in
  arm64) arch="arm64" ;;
  *)     arch="amd64" ;;
esac
stage="$ROOT/dist/deb/${pkg_name}_${pkg_ver}_${arch}"
rm -rf "$stage"
mkdir -p \
  "$stage/DEBIAN" \
  "$stage/opt/grok-bot" \
  "$stage/usr/bin" \
  "$stage/usr/share/applications" \
  "$stage/usr/share/icons/hicolor/256x256/apps" \
  "$stage/usr/lib/grok-bot-linux"

info "Staging $pkg_name $pkg_ver ($arch)"
cp -a "$ROOT/app"/. "$stage/opt/grok-bot"/
if [[ -f "$ROOT/share/grok-bot.png" ]]; then
  install -m 0644 "$ROOT/share/grok-bot.png" "$stage/opt/grok-bot/icon.png"
  install -m 0644 "$ROOT/share/grok-bot.png" "$stage/opt/grok-bot/grok-bot.png"
  install -m 0644 "$ROOT/share/grok-bot.png" "$stage/usr/share/icons/hicolor/256x256/apps/grok-bot.png"
fi
printf '%s\n' "$pkg_ver" > "$stage/opt/grok-bot/GROK_BOT_VERSION"

# Packaging tree used by launch.sh / update.sh
for item in install.sh uninstall.sh launch.sh VERSION Makefile README.md LICENSE scripts share docker; do
  [[ -e "$ROOT/$item" ]] || continue
  cp -a "$ROOT/$item" "$stage/usr/lib/grok-bot-linux/$item"
done
cat > "$stage/usr/lib/grok-bot-linux/install.conf" <<EOF
PREFIX="/usr"
OPT_DIR="/opt/grok-bot"
BIN_DIR="/usr/bin"
DATA_HOME="/usr/share"
SYSTEM="1"
PACKAGING_DIR="/usr/lib/grok-bot-linux"
EOF
chmod 0755 "$stage/usr/lib/grok-bot-linux/launch.sh" \
  "$stage/usr/lib/grok-bot-linux/scripts/"*.sh 2>/dev/null || true

sed -e 's|@PACKAGING@|/usr/lib/grok-bot-linux|' \
  "$ROOT/share/grok-bot-wrapper.in" > "$stage/usr/bin/grok-bot"
chmod 0755 "$stage/usr/bin/grok-bot"

sed -e 's|@BIN@|/usr/bin/grok-bot|' -e 's|@ICON@|/opt/grok-bot/icon.png|' \
  "$ROOT/share/grok-bot.desktop.in" > "$stage/usr/share/applications/grok-bot.desktop"

cat > "$stage/DEBIAN/control" <<EOF
Package: ${pkg_name}
Version: ${pkg_ver}
Section: misc
Priority: optional
Architecture: ${arch}
Maintainer: Grok Bot Linux packagers <user@example.org>
Depends: libgtk-3-0t64 | libgtk-3-0, libnss3, libnotify4, libxss1, libxtst6, xdg-utils, libgbm1, libasound2t64 | libasound2, libdrm2, libxkbcommon0, libxcomposite1, libxdamage1, libxfixes3, libxrandr2, libsecret-1-0, libcups2t64 | libcups2
Recommends: fonts-noto-core, fonts-noto-color-emoji, fonts-noto-cjk, fonts-liberation
Homepage: https://x.ai/bot
Description: Grok Bot desktop (Linux packaging)
 Packaging of the official Grok Bot Linux desktop (verbatim vendor
 payload) plus a launcher, icon, and desktop entry. Vendor also
 publishes grok-bot_*.deb for amd64 and arm64.
EOF

cat > "$stage/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
SANDBOX=/opt/grok-bot/chrome-sandbox
if [ -f "$SANDBOX" ]; then
  chown root:root "$SANDBOX" 2>/dev/null || true
  chmod 4755 "$SANDBOX" 2>/dev/null || true
fi
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
exit 0
EOF
chmod 0755 "$stage/DEBIAN/postinst"

# Drop leftover SUID from a live copy so the archive is portable.
if [[ -u "$stage/opt/grok-bot/chrome-sandbox" ]]; then
  chmod u-s "$stage/opt/grok-bot/chrome-sandbox"
fi
chmod 0755 "$stage/opt/grok-bot/grok-bot" "$stage/opt/grok-bot/chrome-sandbox" 2>/dev/null || true

deb="$ROOT/dist/${pkg_name}_${pkg_ver}_${arch}.deb"
mkdir -p "$ROOT/dist"
info "Building $deb"
dpkg-deb --root-owner-group --build "$stage" "$deb"
info "Built $deb ($(du -h "$deb" | awk '{print $1}'))"
log "Install:  sudo apt install ./dist/${pkg_name}_${pkg_ver}_${arch}.deb"
log "Remove:   sudo apt remove ${pkg_name}"
