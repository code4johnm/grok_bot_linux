#!/usr/bin/env bash
# Ubuntu LTS x86_64 is the canonical apt package list.
# Kali Linux (first-class rolling target) and Debian/Mint reuse it; only
# names that Ubuntu 24.04+ renamed (t64) need an alias. debian_first()
# picks the first name apt can actually install.
#
# Format of DEBIAN_PKG_ALIASES: Ubuntu LTS name first, Debian/Kali fallbacks after.

# Same name on Ubuntu LTS and Debian-family cousins.
DEBIAN_PKGS_COMMON=(
  ca-certificates
  xdg-utils
  locales
  fonts-liberation
  fonts-noto-core
  fonts-noto-mono
  fonts-noto-ui-core
  fonts-noto-color-emoji
  fonts-noto-cjk
  fonts-unifont
  libnss3
  libnotify4
  libxss1
  libxtst6
  libgbm1
  libdrm2
  libxkbcommon0
  libxcomposite1
  libxdamage1
  libxfixes3
  libxrandr2
  libsecret-1-0
  libva2
  libegl1
  libgl1
  libvulkan1
  i965-va-driver
  intel-media-va-driver
  libayatana-appindicator3-1
)

# Ubuntu 24.04/26.04 t64 name, then pre-t64 Debian/Kali name.
DEBIAN_PKG_ALIASES=(
  "libgtk-3-0t64 libgtk-3-0"
  "libasound2t64 libasound2"
  "libcups2t64 libcups2"
  "libatspi2.0-0t64 libatspi2.0-0"
  "libfuse2t64 libfuse2"
)
