#!/usr/bin/env bash
# Install Docker Engine + Compose and add the current user to the docker group.
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

if have docker && docker info >/dev/null 2>&1; then
  info "Docker is already usable"
  docker --version || true
  docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || true
  exit 0
fi

if have docker && [[ "$DRY_RUN" -eq 0 ]]; then
  info "Docker is installed but this user cannot talk to the daemon"
else
  info "Installing Docker packages"
  case "$(os_family)" in
    debian)
      run apt-get update -y
      local_pkgs=(docker.io docker-cli docker-compose containerd)
      run apt-get install -y --no-install-recommends "${local_pkgs[@]}" || \
        run apt-get install -y docker.io docker-compose containerd
      ;;
    fedora)
      run dnf install -y docker docker-compose || run dnf install -y moby-engine docker-compose
      run systemctl enable --now docker
      ;;
    arch)
      run pacman -Sy --needed --noconfirm docker docker-compose
      run systemctl enable --now docker
      ;;
    *)
      die "Unknown distro. Install Docker Engine and Compose, then re-run."
      ;;
  esac
fi

if have systemctl && [[ "$DRY_RUN" -eq 0 ]]; then
  sudo_cmd systemctl enable --now docker 2>/dev/null || \
    sudo_cmd service docker start 2>/dev/null || true
fi

target_user="${SUDO_USER:-$USER}"
if [[ "$target_user" != "root" ]]; then
  info "Adding $target_user to the docker group"
  run usermod -aG docker "$target_user"
  warn "Log out and back in (or run: newgrp docker) before using Docker without sudo."
fi

if [[ "$DRY_RUN" -eq 0 ]]; then
  sudo_cmd docker --version || true
  sudo_cmd docker compose version 2>/dev/null || sudo_cmd docker-compose --version 2>/dev/null || true
fi
info "Docker packages ready"
