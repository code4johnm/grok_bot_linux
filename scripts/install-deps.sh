#!/usr/bin/env bash
# Install Electron/GTK runtime packages plus Intel VA-API drivers.
# Canonical list: Ubuntu LTS x86_64. Debian/Kali reuse it via name aliases.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"
# shellcheck source=scripts/debian-runtime-packages.sh
source "$ROOT/scripts/debian-runtime-packages.sh"

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
  # Prefer an installable candidate. `apt-cache show` also matches packages
  # that are only referred to (Candidate: (none)), which then fails install.
  local p cand
  for p in "$@"; do
    cand="$(apt-cache policy "$p" 2>/dev/null | awk '/Candidate:/ {print $2; exit}')"
    if [[ -n "$cand" && "$cand" != "(none)" ]]; then
      printf '%s\n' "$p"
      return 0
    fi
  done
  return 1
}

install_debian() {
  local id ver
  id="$(os_id)"
  ver="$(os_version_id)"
  info "Installing Ubuntu LTS runtime packages (Debian-compatible aliases for $id $ver)"
  run apt-get update -y
  local pkgs=() p resolved
  for p in "${DEBIAN_PKGS_COMMON[@]}"; do
    if resolved="$(debian_first "$p")"; then
      pkgs+=("$resolved")
    else
      warn "skipping unavailable package: $p"
    fi
  done
  for p in "${DEBIAN_PKG_ALIASES[@]}"; do
    # shellcheck disable=SC2086
    if resolved="$(debian_first $p)"; then
      pkgs+=("$resolved")
    else
      warn "skipping unavailable package set: $p"
    fi
  done
  [[ ${#pkgs[@]} -gt 0 ]] || die "no runtime packages could be resolved"
  run apt-get install -y --no-install-recommends "${pkgs[@]}"
}

install_fedora() {
  warn "Primary target is Ubuntu LTS x86_64; Fedora is best-effort"
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
  warn "Primary target is Ubuntu LTS x86_64; Arch is best-effort"
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
