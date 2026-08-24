#!/usr/bin/env bash
# Install Electron/GTK runtime packages plus Intel VA-API drivers.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'dry-run: %s\n' "$*"
  else
    sudo_cmd "$@"
  fi
}

debian_first() {
  local p
  for p in "$@"; do
    if apt-cache show "$p" >/dev/null 2>&1; then
      printf '%s\n' "$p"
      return 0
    fi
  done
  return 1
}

install_debian() {
  info "Installing Debian/Ubuntu/Kali runtime packages"
  run apt-get update -y
  local pkgs=()
  local p
  for p in \
      ca-certificates \
      xdg-utils \
      locales \
      fonts-liberation \
      fonts-noto-core \
      fonts-noto-mono \
      fonts-noto-ui-core \
      fonts-noto-color-emoji \
      fonts-noto-cjk \
      fonts-unifont \
      libnss3 \
      libnotify4 \
      libxss1 \
      libxtst6 \
      libgbm1 \
      libdrm2 \
      libxkbcommon0 \
      libxcomposite1 \
      libxdamage1 \
      libxfixes3 \
      libxrandr2 \
      libsecret-1-0 \
      libva2 \
      libegl1 \
      libgl1 \
      libvulkan1 \
      i965-va-driver \
      intel-media-va-driver \
      libayatana-appindicator3-1
  do
    debian_first "$p" >/dev/null && pkgs+=("$p")
  done
  debian_first libgtk-3-0t64 libgtk-3-0 >/dev/null && pkgs+=("$(debian_first libgtk-3-0t64 libgtk-3-0)")
  debian_first libasound2t64 libasound2 >/dev/null && pkgs+=("$(debian_first libasound2t64 libasound2)")
  debian_first libcups2t64 libcups2 >/dev/null && pkgs+=("$(debian_first libcups2t64 libcups2)")
  debian_first libatspi2.0-0t64 libatspi2.0-0 >/dev/null && pkgs+=("$(debian_first libatspi2.0-0t64 libatspi2.0-0)")
  debian_first libfuse2t64 libfuse2 >/dev/null && pkgs+=("$(debian_first libfuse2t64 libfuse2)") || true
  run apt-get install -y --no-install-recommends "${pkgs[@]}"
}

install_fedora() {
  info "Installing Fedora/RHEL runtime packages"
  run dnf install -y \
    gtk3 nss libXScrnSaver alsa-lib mesa-libgbm libdrm libxkbcommon \
    libXcomposite libXdamage libXrandr libXfixes libXtst cups-libs \
    libnotify libsecret liberation-fonts google-noto-sans-fonts \
    google-noto-sans-mono-fonts google-noto-emoji-color-fonts \
    google-noto-sans-cjk-fonts unifont-fonts libva libva-intel-driver \
    intel-media-driver xdg-utils at-spi2-atk at-spi2-core vulkan-loader \
    libappindicator-gtk3 || \
  run dnf install -y gtk3 nss alsa-lib mesa-libgbm libdrm libnotify libva xdg-utils \
    google-noto-sans-fonts google-noto-emoji-color-fonts
}

install_arch() {
  info "Installing Arch runtime packages"
  run pacman -Sy --needed --noconfirm \
    gtk3 nss libxss alsa-lib mesa libdrm libxkbcommon libxcomposite \
    libxdamage libxrandr libxtst libxfixes libcups libnotify libsecret \
    ttf-liberation noto-fonts noto-fonts-emoji noto-fonts-cjk ttf-unifont \
    libva libva-intel-driver intel-media-driver xdg-utils \
    at-spi2-core vulkan-icd-loader libappindicator-gtk3
}

case "$(os_family)" in
  debian) install_debian ;;
  fedora) install_fedora ;;
  arch)   install_arch ;;
  *)
    warn "Unknown distro. Install GTK3, nss, alsa, libva, and Intel VA-API drivers yourself."
    [[ "$DRY_RUN" -eq 1 ]] || exit 1
    ;;
esac

info "Runtime packages ready"
