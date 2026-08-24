#!/usr/bin/env bash
# Install grok-bot to ~/.local (default) or /usr/local.
set -euo pipefail

ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PREFIX="${HOME}/.local"
SYSTEM=0
WITH_SYSTEMD=0
UNINSTALL=0

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --prefix DIR    Install prefix (default: ~/.local)
  --system        Install to /usr/local (needs write access)
  --systemd       Install and enable a systemd --user unit
  --uninstall     Remove bin, lib, and the user unit (workspace is kept)
  -h, --help      Show this help

After install:
  export XAI_API_KEY=...    # or GROK_API_KEY; never commit this
  grok-bot ask "Hello"
  grok-bot status
EOF
}

die() { echo "error: $*" >&2; exit 1; }
info() { echo "grok-bot: $*" >&2; }

require_python() {
  local pyver
  if ! command -v python3 >/dev/null 2>&1; then
    die "python3 is required (3.11 or newer)"
  fi
  pyver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
    || die "Python 3.11+ is required (found ${pyver})"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix) PREFIX="${2:?}"; shift 2 ;;
    --system) SYSTEM=1; PREFIX=/usr/local; shift ;;
    --systemd) WITH_SYSTEMD=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

BIN_DIR="${PREFIX}/bin"
LIB_DIR="${PREFIX}/lib/grok-bot"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_PATH="${UNIT_DIR}/grok-bot.service"

uninstall() {
  rm -f "${BIN_DIR}/grok-bot"
  rm -rf "${LIB_DIR}"
  if [[ -f "${UNIT_PATH}" ]]; then
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user disable --now grok-bot.service >/dev/null 2>&1 || true
    fi
    rm -f "${UNIT_PATH}"
    if command -v systemctl >/dev/null 2>&1; then
      systemctl --user daemon-reload >/dev/null 2>&1 || true
    fi
  fi
  info "Removed ${BIN_DIR}/grok-bot and ${LIB_DIR}"
  info "Workspace (~/.local/share/grok-bot) was left in place"
}

if [[ "${UNINSTALL}" -eq 1 ]]; then
  uninstall
  exit 0
fi

require_python
[[ -d "${ROOT}/src/grok_bot" ]] || die "src/grok_bot is missing; run this from the repo checkout"

mkdir -p "${BIN_DIR}" "${LIB_DIR}"
rm -rf "${LIB_DIR}/grok_bot"
cp -a "${ROOT}/src/grok_bot" "${LIB_DIR}/grok_bot"
python3 -m compileall -q "${LIB_DIR}/grok_bot"

cat > "${BIN_DIR}/grok-bot" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="${LIB_DIR}\${PYTHONPATH:+:\${PYTHONPATH}}"
exec python3 -m grok_bot "\$@"
EOF
chmod 0755 "${BIN_DIR}/grok-bot"

info "Installed ${BIN_DIR}/grok-bot"
info "Library ${LIB_DIR}/grok_bot"

if [[ "${WITH_SYSTEMD}" -eq 1 ]]; then
  if ! command -v systemctl >/dev/null 2>&1; then
    die "systemctl not found; install systemd or skip --systemd"
  fi
  mkdir -p "${UNIT_DIR}" "${HOME}/.config/grok-bot"
  cat > "${UNIT_PATH}" <<EOF
[Unit]
Description=grok-bot local daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=${BIN_DIR}/grok-bot daemon --force
Restart=on-failure
RestartSec=2
# Optional file with GROK_API_KEY or XAI_API_KEY (chmod 600). Never commit it.
EnvironmentFile=-%h/.config/grok-bot/env

[Install]
WantedBy=default.target
EOF
  chmod 0644 "${UNIT_PATH}"
  systemctl --user daemon-reload
  systemctl --user enable --now grok-bot.service
  info "Enabled systemd --user unit grok-bot.service"
  info "Put GROK_API_KEY or XAI_API_KEY in ~/.config/grok-bot/env then:"
  info "  systemctl --user restart grok-bot"
fi

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    info "${BIN_DIR} is not on PATH. Add this to your shell rc:"
    echo "  export PATH=\"${BIN_DIR}:\$PATH\"" >&2
    ;;
esac

info "Set an API key and run: grok-bot ask \"Hello\""
info "Check: grok-bot status"
