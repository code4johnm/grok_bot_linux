#!/usr/bin/env bash
# Print the LIBVA_DRIVER_NAME this GPU should use (or empty for default).
set -euo pipefail

if [[ -n "${LIBVA_DRIVER_NAME:-}" ]]; then
  printf '%s\n' "$LIBVA_DRIVER_NAME"
  exit 0
fi

# Intel Gen6–Gen7.5 (Sandy/Ivy/Haswell), Bay Trail, Cherry Trail cannot
# initialize intel-media (iHD, Gen8+). Electron probes iHD first and
# prints: libva error: .../iHD_drv_video.so init failed
for card in /sys/class/drm/card*/device; do
  [[ -f "$card/vendor" && -f "$card/device" ]] || continue
  vendor="$(cat "$card/vendor")"
  device="$(cat "$card/device")"
  [[ "$vendor" == "0x8086" ]] || continue
  id="${device#0x}"
  fam="${id:0:2}"
  case "$fam" in
    01|04|0a|0c|0d|0f|22)
      printf 'i965\n'
      exit 0
      ;;
  esac
done

exit 0
