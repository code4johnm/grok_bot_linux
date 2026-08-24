#!/usr/bin/env bash
# Rocky Linux 9/10 x86_64 is the canonical RHEL-family package list.
# RHEL and AlmaLinux reuse it. Fedora is notes-only, not this list.
# dnf_first() picks the first name dnf/rpm can install.

# Core Electron/GTK runtime (Rocky/RHEL names — not Debian libgtk-3-0 / libasound2).
ROCKY_PKGS_COMMON=(
  gtk3
  libnotify
  nss
  libXScrnSaver
  libXtst
  xdg-utils
  mesa-libgbm
  alsa-lib
  at-spi2-atk
  at-spi2-core
  libdrm
  libxkbcommon
  cups-libs
  libXcomposite
  libXdamage
  libXrandr
  libXfixes
  libsecret
  vulkan-loader
  libva
  liberation-fonts
  ca-certificates
  tar
  curl
)

# Optional: skip if the repo does not carry them (often EPEL / RPM Fusion).
ROCKY_PKGS_OPTIONAL=(
  "libappindicator-gtk3"
  "google-noto-sans-fonts google-noto-fonts-common"
  "google-noto-emoji-color-fonts google-noto-emoji-fonts"
  "google-noto-sans-cjk-fonts google-noto-cjk-fonts"
  "intel-media-driver libva-intel-driver"
  "libva-utils"
)
