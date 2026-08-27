#!/usr/bin/env bash
# Download the official Grok Bot macOS .dmg (version signal for the Linux port).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

REQ_VERSION=""
REQ_ARCH=""
DEST=""

usage() {
  cat <<EOF
Usage: $0 [options]

  --arch arm64|x64   CPU (default: arm64)
  --version X        Pin a desktop version (default: live macOS updater)
  --dest DIR         Output directory (default: $ROOT/dist/official)
  -h, --help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arch) REQ_ARCH="${2:?}"; shift 2 ;;
    --version) REQ_VERSION="${2:?}"; shift 2 ;;
    --dest) DEST="${2:?}"; shift 2 ;;
    macos|darwin|osx|all) shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

DEST="${DEST:-$ROOT/dist/official}"
cpu="${REQ_ARCH:-arm64}"
case "$cpu" in
  arm64|aarch64) cpu=arm64 ;;
  x64|x86_64|amd64|intel) cpu=x64 ;;
  *) die "unsupported arch: $cpu" ;;
esac
args=(--download-only --arch "$cpu" --dest "$DEST")
[[ -n "$REQ_VERSION" ]] && args+=(--version "$REQ_VERSION")
"$ROOT/scripts/install-macos.sh" "${args[@]}"
