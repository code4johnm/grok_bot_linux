#!/usr/bin/env bash
# Build a downloadable stand-alone tarball (app + installer + Docker files).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

WITH_DOCKER_IMAGE=0
[[ "${1:-}" == "--with-docker-image" ]] && WITH_DOCKER_IMAGE=1

"$ROOT/scripts/download-app.sh" "$ROOT/app"
[[ -x "$ROOT/app/grok-bot" ]] || die "app payload missing"

STAGE_NAME="grok_bot_linux-${VERSION}-linux-${UPSTREAM_ARCH}"
STAGE="$ROOT/dist/stage/$STAGE_NAME"
DIST="$ROOT/dist"
rm -rf "$STAGE"
mkdir -p "$STAGE" "$DIST"

info "Staging $STAGE_NAME"
cp -a "$ROOT/install.sh" "$ROOT/uninstall.sh" "$ROOT/launch.sh" "$ROOT/VERSION" "$STAGE/"
cp -a "$ROOT/scripts" "$ROOT/docker" "$ROOT/share" "$STAGE/"
[[ -f "$ROOT/README.md" ]] && cp -a "$ROOT/README.md" "$STAGE/"
[[ -f "$ROOT/LICENSE" ]] && cp -a "$ROOT/LICENSE" "$STAGE/"
[[ -f "$ROOT/Makefile" ]] && cp -a "$ROOT/Makefile" "$STAGE/"
[[ -f "$ROOT/.dockerignore" ]] && cp -a "$ROOT/.dockerignore" "$STAGE/"

mkdir -p "$STAGE/app"
cp -a "$ROOT/app"/. "$STAGE/app"/
chmod 0755 "$STAGE/app/chrome-sandbox" "$STAGE/app/grok-bot" 2>/dev/null || true
chmod 0755 "$STAGE/install.sh" "$STAGE/uninstall.sh" "$STAGE/launch.sh" \
  "$STAGE/scripts/"*.sh "$STAGE/docker/entrypoint.sh" "$STAGE/share/grok-bot-wrapper.in"

# Drop leftover SUID from a live install copy so the archive is portable.
if [[ -u "$STAGE/app/chrome-sandbox" ]]; then
  chmod u-s "$STAGE/app/chrome-sandbox"
fi

ARCHIVE="$DIST/${STAGE_NAME}.tar.gz"
info "Writing $ARCHIVE"
tar -C "$DIST/stage" --owner=0 --group=0 --numeric-owner -czf "$ARCHIVE" "$STAGE_NAME"

(
  cd "$DIST"
  sha256sum "${STAGE_NAME}.tar.gz" > SHA256SUMS
)

info "Archive size: $(du -h "$ARCHIVE" | awk '{print $1}')"
cat "$DIST/SHA256SUMS"

if [[ "$WITH_DOCKER_IMAGE" -eq 1 ]]; then
  have docker || die "docker is required for --with-docker-image"
  info "Building Docker image grok-bot-linux:${VERSION}"
  docker build -t "grok-bot-linux:${VERSION}" -f "$ROOT/docker/Dockerfile" "$ROOT"
  img="$DIST/grok_bot_linux-${VERSION}-docker.tar.gz"
  info "Saving $img"
  docker save "grok-bot-linux:${VERSION}" | gzip > "$img"
  (
    cd "$DIST"
    sha256sum "$(basename "$img")" >> SHA256SUMS
  )
fi

info "Stand-alone package is ready in $DIST"
log "Install on another machine:"
log "  tar -xzf $ARCHIVE"
log "  cd $STAGE_NAME"
log "  ./install.sh --with-docker"
