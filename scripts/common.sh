#!/usr/bin/env bash
# Shared helpers. Source after ROOT is set, or from scripts/.
set -euo pipefail

if [[ -z "${ROOT:-}" ]]; then
  _COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  ROOT="$(cd "$_COMMON_DIR/.." && pwd)"
fi

VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || echo 0.24.0)"
APP_NAME="Grok Bot"
APP_ID="grok-bot"
DEFAULT_OPT_DIR="${GROK_BOT_HOME:-$HOME/.local/opt/grok-bot}"
DEFAULT_PACKAGING_DIR="${GROK_BOT_LINUX_HOME:-$HOME/.local/opt/grok_bot_linux}"

# Wrapper GitHub repo is taken from origin (or GROK_BOT_LINUX_REPO). Not hardcoded.
git_origin_repo() {
  local url
  url="$(git -C "${1:-$ROOT}" remote get-url origin 2>/dev/null || true)"
  [[ -n "$url" ]] || return 1
  printf '%s\n' "$url" | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?.*#\1#'
}

WRAPPER_REPO="${GROK_BOT_LINUX_REPO:-$(git_origin_repo "$ROOT" 2>/dev/null || true)}"
UPSTREAM_REPO="Nichokas/grokbot-linux-port"
if [[ -n "$WRAPPER_REPO" ]]; then
  WRAPPER_COMMIT_API="https://api.github.com/repos/${WRAPPER_REPO}/commits/main"
  WRAPPER_TARBALL_URL="https://github.com/${WRAPPER_REPO}/archive/refs/heads/main.tar.gz"
else
  WRAPPER_COMMIT_API=""
  WRAPPER_TARBALL_URL=""
fi
UPSTREAM_LATEST_API="https://api.github.com/repos/${UPSTREAM_REPO}/releases/latest"

CACHE_DIR="${GROK_BOT_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/grok-bot}"

KNOWN_UPSTREAM_SHA256_0_24_0="f6b6495f9398a9d60702a282b404ac52e2b1c1c345d3ba81bbbd242e49ea6aad"

set_upstream_version() {
  VERSION="$(ver_norm "${1:-$VERSION}")"
  UPSTREAM_TAG="v${VERSION}"
  UPSTREAM_TARBALL="Grok_Bot_${VERSION}_linux_x64.tar.gz"
  UPSTREAM_URL="https://github.com/${UPSTREAM_REPO}/releases/download/${UPSTREAM_TAG}/${UPSTREAM_TARBALL}"
  case "$VERSION" in
    0.24.0) UPSTREAM_SHA256="$KNOWN_UPSTREAM_SHA256_0_24_0" ;;
    *)      UPSTREAM_SHA256="" ;;
  esac
}

ver_norm() {
  local v="${1:-}"
  v="${v#v}"
  printf '%s\n' "$v"
}

# True if $1 is a newer semver than $2 (v-prefix ignored). Equal is false.
ver_gt() {
  local a b
  a="$(ver_norm "$1")"
  b="$(ver_norm "$2")"
  [[ -n "$a" && -n "$b" && "$a" != "$b" ]] || return 1
  [[ "$(printf '%s\n%s\n' "$a" "$b" | sort -V | tail -n1)" == "$a" ]]
}

set_upstream_version "$VERSION"

log()  { printf '%s\n' "$*"; }
info() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

is_root() { [[ "$(id -u)" -eq 0 ]]; }

sudo_cmd() {
  if is_root; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    die "need root or sudo for: $*"
  fi
}

# Non-interactive sudo: succeeds only if a password is not required.
sudo_n() {
  if is_root; then
    "$@"
  elif have sudo && sudo -n true >/dev/null 2>&1; then
    sudo -n "$@"
  else
    return 1
  fi
}

os_family() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID_LIKE:-$ID}" in
      *debian*|*ubuntu*|*linuxmint*|kali) echo debian ;;
      *rhel*|*fedora*|*centos*)           echo fedora ;;
      *arch*|arch)                        echo arch ;;
      *)
        case "$ID" in
          debian|ubuntu|kali|linuxmint) echo debian ;;
          fedora|rhel|centos|rocky|almalinux) echo fedora ;;
          arch|manjaro|endeavouros) echo arch ;;
          *) echo unknown ;;
        esac
        ;;
    esac
  else
    echo unknown
  fi
}

http_get() {
  local url="$1"
  if have curl; then
    curl -fsSL -A 'grok-bot-linux' --retry 3 --retry-delay 2 "$url"
  elif have wget; then
    wget -qO- --user-agent='grok-bot-linux' "$url"
  else
    die "need curl or wget"
  fi
}

http_download() {
  local url="$1" dest="$2"
  if have curl; then
    curl -fL -A 'grok-bot-linux' --retry 3 --retry-delay 2 -o "$dest" "$url"
  elif have wget; then
    wget --user-agent='grok-bot-linux' -O "$dest" "$url"
  else
    die "need curl or wget"
  fi
}

app_is_running() {
  local dir="${1:-$DEFAULT_OPT_DIR}"
  [[ -n "$dir" ]] || return 1
  pgrep -f "$dir/grok-bot" >/dev/null 2>&1
}

notify_user() {
  [[ "${NOTIFY:-0}" == "1" ]] || return 0
  have notify-send || return 0
  notify-send -a "Grok Bot" -i grok-bot "Grok Bot" "$*" >/dev/null 2>&1 || true
}

installed_app_version() {
  local dir="${1:-$DEFAULT_OPT_DIR}"
  if [[ -f "$dir/GROK_BOT_VERSION" ]]; then
    tr -d '[:space:]' < "$dir/GROK_BOT_VERSION"
  elif [[ -f "$ROOT/VERSION" ]]; then
    tr -d '[:space:]' < "$ROOT/VERSION"
  else
    printf '%s\n' "$VERSION"
  fi
}

wrapper_revision() {
  local dir="${1:-$ROOT}"
  if [[ -f "$dir/.wrapper-revision" ]]; then
    tr -d '[:space:]' < "$dir/.wrapper-revision"
  elif git -C "$dir" rev-parse HEAD >/dev/null 2>&1; then
    git -C "$dir" rev-parse HEAD
  else
    printf 'unknown\n'
  fi
}

# Print: version<TAB>url<TAB>sha256  for the latest Nichokas Linux tarball.
latest_upstream_release() {
  have python3 || return 1
  http_get "$UPSTREAM_LATEST_API" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if d.get("draft") or d.get("prerelease"):
    sys.exit("latest GitHub release is a draft/prerelease")
tag = d.get("tag_name", "").lstrip("v")
url = sha = ""
for a in d.get("assets") or []:
    name = a.get("name") or ""
    if name.endswith("_linux_x64.tar.gz"):
        url = a.get("browser_download_url") or ""
        dig = a.get("digest") or ""
        if dig.startswith("sha256:"):
            sha = dig.split(":", 1)[1]
        break
if not tag or not url:
    sys.exit("could not find a linux-x64 tarball on the latest release")
print(f"{tag}\t{url}\t{sha}")
'
}

latest_wrapper_sha() {
  [[ -n "${WRAPPER_COMMIT_API:-}" ]] || return 1
  have python3 || return 1
  http_get "$WRAPPER_COMMIT_API" | python3 -c 'import json,sys; print(json.load(sys.stdin)["sha"])'
}
