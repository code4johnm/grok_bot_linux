#!/usr/bin/env bash
# TUI-only: grok-bot-tui. No Electron desktop. Safe on aarch64 and x86_64.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

usage() {
  cat <<EOF
Usage: $0

Install grok-bot-tui only (pip editable + grok-bot-tui on PATH).
Does not install Electron grok-bot. Intended for aarch64 (Pi 4/5, SBCs)
and x86_64.

  grok-bot-tui
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --tui-only) shift ;;
    *) die "unknown option: $1 (this script is TUI-only; see --help)" ;;
  esac
done

have python3 || die "python3 is required (3.11+)"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Python 3.11+ is required"

ARCH="$(uname -m)"
info "Installing grok-bot-tui (TUI only, no Electron) on ${ARCH}"

if [[ "$ARCH" != "x86_64" && "$ARCH" != "amd64" ]]; then
  info "Electron grok-bot desktop is x86_64 only; not installing it."
fi

python3 -m pip install --user -e "$ROOT/grok-bot-tui"

BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"
if [[ ! -x "$BIN_DIR/grok-bot-tui" ]] && ! have grok-bot-tui; then
  cat > "$BIN_DIR/grok-bot-tui" <<'EOF'
#!/usr/bin/env bash
exec python3 -m grok_bot_tui "$@"
EOF
  chmod 0755 "$BIN_DIR/grok-bot-tui"
fi

info "grok-bot-tui installed. Ensure ${BIN_DIR} is on PATH, then run: grok-bot-tui"
if have grok-bot-tui; then
  grok-bot-tui --help | head -n 6 || true
fi
