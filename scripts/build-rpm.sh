#!/usr/bin/env bash
# Build an x86_64 .rpm for Rocky Linux 9/10 (RHEL-family).
# Layout: /opt/grok-bot, /usr/bin/grok-bot, /usr/share/applications
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

have rpmbuild || die "rpmbuild is required to build an .rpm (rpm-build package)"

"$ROOT/scripts/download-app.sh" "$ROOT/app"
[[ -x "$ROOT/app/grok-bot" ]] || die "app payload missing"

pkg_name="grok-bot"
pkg_ver="$VERSION"
pkg_rel="1"
arch="x86_64"
top="$ROOT/dist/rpmbuild"
rm -rf "$top"
mkdir -p "$top"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

stage="$top/BUILD/${pkg_name}-${pkg_ver}"
mkdir -p \
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
if [[ -u "$stage/opt/grok-bot/chrome-sandbox" ]]; then
  chmod u-s "$stage/opt/grok-bot/chrome-sandbox"
fi
chmod 0755 "$stage/opt/grok-bot/grok-bot" "$stage/opt/grok-bot/chrome-sandbox" 2>/dev/null || true

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

# Tarball the staged tree for rpmbuild %setup
tar -C "$top/BUILD" -czf "$top/SOURCES/${pkg_name}-${pkg_ver}.tar.gz" "${pkg_name}-${pkg_ver}"

cat > "$top/SPECS/${pkg_name}.spec" <<EOF
Name:           ${pkg_name}
Version:        ${pkg_ver}
Release:        ${pkg_rel}%{?dist}
Summary:        Grok Bot desktop (community Linux port)
License:        Proprietary and MIT
URL:            https://x.ai/bot
Source0:        %{name}-%{version}.tar.gz
BuildArch:      ${arch}

Requires:       gtk3
Requires:       nss
Requires:       libnotify
Requires:       libXScrnSaver
Requires:       libXtst
Requires:       xdg-utils
Requires:       mesa-libgbm
Requires:       alsa-lib
Requires:       at-spi2-atk
Requires:       at-spi2-core
Requires:       libdrm
Requires:       libxkbcommon
Requires:       cups-libs
Requires:       libXcomposite
Requires:       libXdamage
Requires:       libXrandr
Requires:       libXfixes

%description
Community Linux packaging of the official Grok Bot desktop app for
Rocky Linux 9/10 (x86_64). There is no official vendor RPM.

%prep
%setup -q

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a opt usr %{buildroot}/

%post
SANDBOX=/opt/grok-bot/chrome-sandbox
if [ -f "\$SANDBOX" ]; then
  chown root:root "\$SANDBOX" 2>/dev/null || true
  chmod 4755 "\$SANDBOX" 2>/dev/null || true
fi
if command -v restorecon >/dev/null 2>&1 && [ "\$(getenforce 2>/dev/null)" = "Enforcing" ]; then
  restorecon -Rv /opt/grok-bot >/dev/null 2>&1 || true
fi
command -v update-desktop-database >/dev/null && update-desktop-database -q /usr/share/applications || true
exit 0

%files
%dir /opt/grok-bot
/opt/grok-bot
/usr/bin/grok-bot
/usr/share/applications/grok-bot.desktop
/usr/share/icons/hicolor/256x256/apps/grok-bot.png
/usr/lib/grok-bot-linux

%changelog
* $(date '+%a %b %d %Y') Grok Bot Linux packagers <user@example.org> - ${pkg_ver}-${pkg_rel}
- Community Linux port package for Rocky Linux
EOF

info "Building RPM"
rpmbuild --define "_topdir $top" -bb "$top/SPECS/${pkg_name}.spec"
mapfile -t rpms < <(find "$top/RPMS" -name '*.rpm' -type f)
[[ ${#rpms[@]} -gt 0 ]] || die "rpmbuild produced no rpm"
mkdir -p "$ROOT/dist"
for r in "${rpms[@]}"; do
  cp -a "$r" "$ROOT/dist/"
  info "Built dist/$(basename "$r") ($(du -h "$r" | awk '{print $1}'))"
done
log "Install:  sudo dnf install ./dist/${pkg_name}-${pkg_ver}-*.rpm"
log "Remove:   sudo dnf remove ${pkg_name}"
