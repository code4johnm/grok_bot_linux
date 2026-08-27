#!/usr/bin/env bash
# Report the official macOS Grok Bot version and the Linux community port.
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
linux_latest=""
if rel="$(latest_upstream_release || true)"; then
  linux_latest="${rel%%$'\t'*}"
fi

macos_row() {
  local cpu="$1"
  local rel ver url
  if rel="$(latest_macos_release "$cpu" 2>/dev/null)"; then
    ver="${rel%%$'\t'*}"
    url="${rel#*$'\t'}"
    printf '%s\t%s\t%s\n' "$cpu" "$ver" "$url"
  else
    printf '%s\t%s\t%s\n' "$cpu" "unavailable" ""
  fi
}

macos_arm="$(macos_row arm64)"
macos_x64="$(macos_row x64)"

if [[ "$JSON" -eq 1 ]]; then
  python3 - "$linux_local" "${linux_latest:-}" "$macos_arm" "$macos_x64" <<'PY'
import json, sys
linux_local, linux_latest, macos_arm, macos_x64 = sys.argv[1:5]

def split_row(s):
    parts = s.split("\t")
    while len(parts) < 3:
        parts.append("")
    return {"arch": parts[0], "version": parts[1], "url": parts[2]}

print(json.dumps({
    "linux": {"local": linux_local, "latest": linux_latest, "channel": "community-port"},
    "macos": [split_row(macos_arm), split_row(macos_x64)],
}, indent=2))
PY
else
  fmt() {
    local cpu ver url
    IFS=$'\t' read -r cpu ver url <<<"$1"
    printf 'macos    %-6s %s  %s\n' "$cpu" "$ver" "$url"
  }
  echo "linux    local=$linux_local  latest=${linux_latest:-unknown}  community port (tracks macOS)"
  fmt "$macos_arm"
  fmt "$macos_x64"
fi

if [[ "$FAIL_IF_NEWER" -eq 1 ]]; then
  newer=0
  desk_ver="${macos_arm#*$'\t'}"; desk_ver="${desk_ver%%$'\t'*}"
  if [[ -n "$desk_ver" && "$desk_ver" != "unavailable" ]] && ver_gt "$desk_ver" "$linux_local"; then
    newer=1
  fi
  if [[ -n "$linux_latest" ]] && ver_gt "$linux_latest" "$linux_local"; then
    newer=1
  fi
  exit "$newer"
fi
