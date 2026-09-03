#!/usr/bin/env bash
# Populate DEST with the Grok Bot Electron tree.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

FORCE=0
SKIP_LOCAL=0
REQ_VERSION=""
DEST=""

usage() {
  cat <<EOF
Usage: $0 [options] [DEST]

  DEST               Extract here (default: $ROOT/app)
  --force            Replace DEST even if grok-bot is already there
  --skip-local       Do not copy from an existing install at $DEFAULT_OPT_DIR
  --version X        Fetch Grok Bot X instead of VERSION
  -h, --help         Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --skip-local) SKIP_LOCAL=1; shift ;;
    --version) REQ_VERSION="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown option: $1" ;;
    *) DEST="$1"; shift ;;
  esac
done
[[ $# -eq 0 ]] || DEST="${DEST:-$1}"

DEST="${DEST:-$ROOT/app}"
[[ -n "$REQ_VERSION" ]] && set_upstream_version "$REQ_VERSION"

CACHE="${GROK_BOT_CACHE:-$CACHE_DIR}"
mkdir -p "$CACHE" "$DEST"

if [[ "$FORCE" -eq 0 && -x "$DEST/grok-bot" && -f "$DEST/chrome_100_percent.pak" ]]; then
  info "App already present at $DEST"
  exit 0
fi

if [[ "$FORCE" -eq 0 && "$SKIP_LOCAL" -eq 0 && -x "$DEFAULT_OPT_DIR/grok-bot" && -f "$DEFAULT_OPT_DIR/chrome_100_percent.pak" ]]; then
  info "Copying installed app from $DEFAULT_OPT_DIR"
  mkdir -p "$DEST"
  cp -a "$DEFAULT_OPT_DIR"/. "$DEST"/
  chmod 755 "$DEST/chrome-sandbox" 2>/dev/null || true
  exit 0
fi

if [[ -z "$UPSTREAM_SHA256" ]]; then
  info "Looking up checksum for $UPSTREAM_TARBALL"
  rel="$(latest_upstream_release || true)"
  if [[ -n "$rel" ]]; then
    rel_ver="${rel%%$'\t'*}"
    rest="${rel#*$'\t'}"
    rel_url="${rest%%$'\t'*}"
    rel_sha="${rest#*$'\t'}"
    if [[ "$(ver_norm "$rel_ver")" == "$VERSION" ]]; then
      UPSTREAM_URL="${rel_url:-$UPSTREAM_URL}"
      UPSTREAM_SHA256="$rel_sha"
    fi
  fi
fi

archive="$CACHE/$UPSTREAM_TARBALL"
info "Downloading $UPSTREAM_TARBALL (linux-${UPSTREAM_ARCH})"
http_download "$UPSTREAM_URL" "$archive"

if have sha256sum; then
  got="$(sha256sum "$archive" | awk '{print $1}')"
  if [[ -n "$UPSTREAM_SHA256" && "$got" != "$UPSTREAM_SHA256" ]]; then
    rm -f "$archive"
    die "checksum mismatch for $UPSTREAM_TARBALL (got $got)"
  elif [[ -z "$UPSTREAM_SHA256" ]]; then
    warn "no checksum published for $UPSTREAM_TARBALL; recorded $got"
    UPSTREAM_SHA256="$got"
  fi
else
  warn "sha256sum not found; skipping checksum"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -xzf "$archive" -C "$tmp"
# 0.30.0+ tarballs ship the Electron tree under payload/ (verbatim official .deb).
inner=""
while IFS= read -r -d '' f; do
  d="$(dirname "$f")"
  if [[ -f "$d/chrome-sandbox" || -f "$d/chrome_100_percent.pak" ]]; then
    inner="$f"
    break
  fi
done < <(find "$tmp" -maxdepth 5 -type f -name grok-bot -perm -111 -print0 2>/dev/null)
if [[ -z "$inner" ]]; then
  inner="$(find "$tmp" -maxdepth 5 -type f -name grok-bot -perm -111 | head -n1)"
fi
[[ -n "$inner" ]] || die "downloaded archive did not contain grok-bot"
src="$(dirname "$inner")"
mkdir -p "$DEST"
if [[ "$FORCE" -eq 1 ]]; then
  find "$DEST" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi
cp -a "$src"/. "$DEST"/
chmod 755 "$DEST/chrome-sandbox" 2>/dev/null || true
printf '%s\n' "$VERSION" > "$DEST/GROK_BOT_VERSION"
info "App extracted to $DEST"
