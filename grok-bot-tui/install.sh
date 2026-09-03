#!/usr/bin/env bash
# grok-tui-shell installer: Ubuntu, Kali, Rocky Linux, Raspberry Pi OS.
# User install by default. No Electron. No Kali metapackages. Do not live as root.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
if [[ ! -f "$HERE/pyproject.toml" ]]; then
  echo "error: run this script from the grok-bot-tui tree" >&2
  exit 1
fi

info() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

MODE="user"
AUTOSTART=0
ASSUME_YES=0
TUI_ONLY=1

usage() {
  cat <<EOF
Usage: $0 [options]

Install grok-tui-shell (package grok-bot-tui) on:
  Ubuntu, Kali Linux, Rocky Linux, Raspberry Pi OS / Ubuntu on Raspberry Pi

Detects OS + architecture (x86_64, aarch64, armv7l) and uses apt or dnf.
Does not install Electron grok-bot (desktop is a separate installer).
Does not install Kali offensive metapackages.

Options:
  --user           Install for this user (default). pip --user + ~/.local
  --system         pip system /usr/local (requires root). Prefer --user on Kali/Pi.
  --autostart      Install tmux + systemd --user unit, enable on boot (Pi)
  --no-autostart   Skip systemd (default)
  --yes, -y        Non-interactive package installs
  --tui-only       Accepted for compatibility; this installer is always TUI-only
  -h, --help

After install:
  export PATH="\$HOME/.local/bin:\$PATH"
  grok-tui-shell status
  grok-tui-shell              # TUI (needs a TTY)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --user) MODE="user"; shift ;;
    --system) MODE="system"; shift ;;
    --autostart) AUTOSTART=1; shift ;;
    --no-autostart) AUTOSTART=0; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --tui-only) TUI_ONLY=1; shift ;;
    *) die "unknown option: $1 (see --help)" ;;
  esac
done

# --- detect OS / arch / package manager ---
ARCH="$(uname -m)"
ID=""
ID_LIKE=""
PRETTY=""
if [[ -f /etc/os-release ]]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  ID="${ID:-}"
  ID_LIKE="${ID_LIKE:-}"
  PRETTY="${PRETTY_NAME:-$ID}"
fi

is_pi() {
  if [[ -r /proc/device-tree/model ]] && grep -qi raspberry /proc/device-tree/model 2>/dev/null; then
    return 0
  fi
  [[ -f /etc/rpi-issue ]] && return 0
  case "${ID}|${ID_LIKE}" in
    *raspbian*|*raspberry*) return 0 ;;
  esac
  return 1
}

PM=""
FAMILY=""
case "${ID}" in
  rocky|rhel|almalinux|centos|fedora)
    FAMILY="rhel"
    PM="dnf"
    ;;
  kali)
    FAMILY="kali"
    PM="apt"
    ;;
  ubuntu|linuxmint|debian|raspbian)
    FAMILY="${ID}"
    PM="apt"
    ;;
  *)
    case "${ID_LIKE}" in
      *rhel*|*fedora*|*centos*) FAMILY="rhel"; PM="dnf" ;;
      *debian*) FAMILY="debian"; PM="apt" ;;
      *)
        if have dnf; then FAMILY="rhel"; PM="dnf"
        elif have apt-get; then FAMILY="debian"; PM="apt"
        else die "unsupported OS (need apt or dnf). uname=$(uname -a)"
        fi
        ;;
    esac
    ;;
esac

if is_pi; then
  FAMILY="raspberrypi"
fi

case "$ARCH" in
  x86_64|amd64|aarch64|arm64|armv7l|armv6l|armhf) ;;
  *) warn "unrecognized architecture ${ARCH}; continuing anyway" ;;
esac

info "OS: ${PRETTY:-unknown}  family=${FAMILY}  arch=${ARCH}  pm=${PM}"
if [[ "$ARCH" == "x86_64" || "$ARCH" == "amd64" || "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then
  info "Electron grok-bot desktop is available on this arch (install separately)."
else
  info "32-bit ARM: TUI only. grok-bot Electron needs x86_64 or aarch64."
fi

if [[ "$(id -u)" -eq 0 && "$MODE" == "user" ]]; then
  warn "running as root with --user; on Kali/Pi prefer a normal login user."
fi
if [[ "$MODE" == "system" && "$(id -u)" -ne 0 ]]; then
  die "--system needs root (sudo $0 --system)"
fi

sudo_wrap() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    die "need root or sudo to install packages"
  fi
}

apt_install() {
  local pkgs=("$@")
  local flags=(-y)
  [[ "$ASSUME_YES" -eq 1 ]] || flags=(-y)
  sudo_wrap apt-get update -qq
  sudo_wrap apt-get install "${flags[@]}" --no-install-recommends "${pkgs[@]}"
}

dnf_install() {
  local pkgs=("$@")
  if [[ "$ASSUME_YES" -eq 1 ]]; then
    sudo_wrap dnf install -y "${pkgs[@]}"
  else
    sudo_wrap dnf install -y "${pkgs[@]}"
  fi
}

# --- OS packages (small set; never Kali metapackages) ---
PY_PKGS=()
EXTRA=()
if [[ "$PM" == "apt" ]]; then
  PY_PKGS=(python3 python3-pip python3-venv ca-certificates)
  [[ "$AUTOSTART" -eq 1 ]] && EXTRA+=(tmux)
  info "Installing packages via apt: ${PY_PKGS[*]} ${EXTRA[*]}"
  apt_install "${PY_PKGS[@]}" ${EXTRA[@]+"${EXTRA[@]}"}
else
  PY_PKGS=(python3 python3-pip ca-certificates)
  [[ "$AUTOSTART" -eq 1 ]] && EXTRA+=(tmux)
  info "Installing packages via dnf: ${PY_PKGS[*]} ${EXTRA[*]}"
  dnf_install "${PY_PKGS[@]}" ${EXTRA[@]+"${EXTRA[@]}"}
fi

have python3 || die "python3 is required"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
  || die "Python 3.9+ is required (Raspberry Pi OS Bookworm or Ubuntu 20.04+)"

# --- pip install (venv optional; --user keeps Pi footprint in $HOME) ---
export PATH="${XDG_BIN_HOME:-$HOME/.local/bin}:$PATH"
PIP=(python3 -m pip)
if [[ "$MODE" == "system" ]]; then
  info "pip install grok-bot-tui (system)"
  "${PIP[@]}" install --upgrade pip setuptools wheel >/dev/null 2>&1 || true
  "${PIP[@]}" install "$HERE"
else
  info "pip install --user -e grok-bot-tui"
  "${PIP[@]}" install --user --upgrade pip setuptools wheel >/dev/null 2>&1 || true
  "${PIP[@]}" install --user -e "$HERE"
fi

BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
if [[ "$MODE" == "system" ]]; then
  BIN_DIR="/usr/local/bin"
fi
mkdir -p "$BIN_DIR"
if [[ ! -x "$BIN_DIR/grok-tui-shell" ]]; then
  cat > "$BIN_DIR/grok-tui-shell" <<'EOF'
#!/usr/bin/env bash
exec python3 -m grok_bot_tui "$@"
EOF
  chmod 0755 "$BIN_DIR/grok-tui-shell"
fi
ln -sfn "$BIN_DIR/grok-tui-shell" "$BIN_DIR/grok-bot-tui"

# --- config + man ---
python3 - <<'PY'
from grok_bot_tui.config import write_default_config
path = write_default_config()
print("config", path)
PY

MAN_SRC="$HERE/share/man/man1/grok-tui-shell.1"
if [[ "$MODE" == "system" ]]; then
  MAN_DIR="/usr/local/share/man/man1"
else
  MAN_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/man/man1"
fi
if [[ -f "$MAN_SRC" ]]; then
  mkdir -p "$MAN_DIR"
  cp "$MAN_SRC" "$MAN_DIR/grok-tui-shell.1"
  ln -sfn "$MAN_DIR/grok-tui-shell.1" "$MAN_DIR/grok-bot-tui.1"
  info "man page: $MAN_DIR/grok-tui-shell.1  (man grok-tui-shell)"
fi

# --- systemd user autostart (especially Raspberry Pi) ---
if [[ "$AUTOSTART" -eq 1 ]]; then
  have tmux || die "--autostart needs tmux (package install may have failed)"
  UNIT_SRC="$HERE/share/grok-tui-shell.service"
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  mkdir -p "$UNIT_DIR"
  cp "$UNIT_SRC" "$UNIT_DIR/grok-tui-shell.service"
  systemctl --user daemon-reload || warn "systemctl --user daemon-reload failed (no user bus yet)"
  systemctl --user enable grok-tui-shell.service || warn "enable failed"
  systemctl --user start grok-tui-shell.service || warn "start failed (ok if no user session); enable linger"
  if have loginctl; then
    loginctl enable-linger "$USER" 2>/dev/null || warn "could not enable linger (need a login seat). On Pi: sudo loginctl enable-linger $USER"
  fi
  info "autostart: systemctl --user status grok-tui-shell.service"
  info "attach TUI: tmux attach -t grok-tui"
fi

info "installed grok-tui-shell on ${FAMILY}/${ARCH}"
info "PATH: export PATH=\"$BIN_DIR:\$PATH\""
info "try: grok-tui-shell status"
info "TUI: grok-tui-shell     (needs a terminal; SSH is fine)"
info "guide: $HERE/README.md"
if have grok-tui-shell; then
  grok-tui-shell version || python3 -m grok_bot_tui version
fi
# silence unused
: "$TUI_ONLY" "$ROOT"
