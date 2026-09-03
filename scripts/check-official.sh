#!/usr/bin/env bash
# Compare local VERSION to official Linux Grok Bot and the community tarball.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

JSON=0
FAIL_IF_NEWER=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json) JSON=1; shift ;;
    --fail-if-newer) FAIL_IF_NEWER=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--json] [--fail-if-newer]"
      exit 0
      ;;
    *) die "unknown option: $1" ;;
  esac
done

linux_local="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || echo unknown)"

official_row() {
  local arch="$1"
  local rel ver rest
  if rel="$(latest_official_linux "$arch" 2>/dev/null)"; then
    ver="${rel%%$'\t'*}"
    rest="${rel#*$'\t'}"
    printf '%s\t%s\t%s\n' "$arch" "$ver" "${rest%%$'\t'*}"
  else
    printf '%s\t%s\t%s\n' "$arch" "unavailable" ""
  fi
}

community_row() {
  local arch="$1"
  local rel ver rest
  if rel="$(latest_upstream_release "$arch" 2>/dev/null)"; then
    ver="${rel%%$'\t'*}"
    rest="${rel#*$'\t'}"
    printf '%s\t%s\t%s\n' "$arch" "$ver" "${rest%%$'\t'*}"
  else
    printf '%s\t%s\t%s\n' "$arch" "unavailable" ""
  fi
}

off_x64="$(official_row x64)"
off_arm="$(official_row arm64)"
com_x64="$(community_row x64)"
com_arm="$(community_row arm64)"

if [[ "$JSON" -eq 1 ]]; then
  python3 - "$linux_local" "$off_x64" "$off_arm" "$com_x64" "$com_arm" <<'PY'
import json, sys
local, off_x64, off_arm, com_x64, com_arm = sys.argv[1:6]

def split_row(s):
    parts = s.split("\t")
    while len(parts) < 3:
        parts.append("")
    return {"arch": parts[0], "version": parts[1], "url": parts[2]}

print(json.dumps({
    "local": local,
    "official": [split_row(off_x64), split_row(off_arm)],
    "community_port": [split_row(com_x64), split_row(com_arm)],
}, indent=2))
PY
else
  fmt() {
    local kind="$1" row="$2"
    local arch ver url
    IFS=$'\t' read -r arch ver url <<<"$row"
    printf '%-16s %-6s %s  %s\n' "$kind" "$arch" "$ver" "$url"
  }
  echo "local            -      $linux_local"
  fmt official "$off_x64"
  fmt official "$off_arm"
  fmt community-port "$com_x64"
  fmt community-port "$com_arm"
fi

if [[ "$FAIL_IF_NEWER" -eq 1 ]]; then
  newer=0
  for row in "$off_x64" "$off_arm" "$com_x64" "$com_arm"; do
    ver="${row#*$'\t'}"
    ver="${ver%%$'\t'*}"
    if [[ -n "$ver" && "$ver" != "unavailable" ]] && ver_gt "$ver" "$linux_local"; then
      newer=1
    fi
  done
  exit "$newer"
fi
