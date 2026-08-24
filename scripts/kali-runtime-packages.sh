#!/usr/bin/env bash
# Kali Linux x86_64 (Debian/rolling). Not Ubuntu.
# Probe classic Debian names first with apt-cache policy, then Kali/t64
# equivalents. debian_first() records the first name that has a Candidate.

# Names that match Ubuntu LTS and Kali without a t64 rename.
KALI_PKGS_COMMON=(
  ca-certificates
  xdg-utils
  locales
  fonts-liberation
  fonts-noto-core
  fonts-noto-mono
  fonts-noto-color-emoji
  fonts-noto-cjk
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
)

# Debian/classic name first (what docs quote), then Kali rolling equivalent.
# Recorded in README when the first name has Candidate: (none).
KALI_PKG_ALIASES=(
  "libgtk-3-0 libgtk-3-0t64"
  "libasound2 libasound2t64"
  "libatk-bridge2.0-0 libatk-bridge2.0-0t64"
  "libatspi2.0-0 libatspi2.0-0t64"
  "libcups2 libcups2t64"
  "libfuse2 libfuse2t64"
)
