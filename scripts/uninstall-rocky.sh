#!/usr/bin/env bash
# Rocky/RHEL uninstall. Same files as Ubuntu; SELinux labels are left alone
# (do not setenforce 0). Does not remove the official CLI or user data.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

if is_root; then
  rm -f /etc/profile.d/grok.sh 2>/dev/null || true
fi
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/environment.d/grok.conf" 2>/dev/null || true

exec "$ROOT/uninstall.sh" "$@"
