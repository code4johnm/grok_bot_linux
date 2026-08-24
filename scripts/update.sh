#!/usr/bin/env bash
# Update grok_bot_linux (this wrapper), the Grok Bot app, and runtime packages.
set -euo pipefail
if [[ -z "${GROK_BOT_UPDATE_INNER:-}" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

AUTO=0
NOTIFY=0
CHECK_ONLY=0
DO_SELF=1
DO_APP=1
DO_DEPS=1
FORCE=0

usage() {
  cat <<EOF
Usage: $0 [options]

Update this Linux package, the Grok Bot app, and its OS dependencies
when a newer version is available.

  --check          Report available updates; do not install
  --auto           Quiet unattended mode (skip sudo prompts, stage a
                   running app until next launch)
  --notify         Send a desktop notification with the result
  --self-only      Only update grok_bot_linux (launcher, scripts, icon)
  --app-only       Only update the Grok Bot Electron app
  --deps-only      Only refresh GTK/NSS/VA-API packages
  --force          Re-install even when versions already match
  -h, --help       Show this help

Manual:
  grok-bot update
  $ROOT/scripts/update.sh

Auto: a systemd user timer (daily) plus a once-a-day check when you
launch grok-bot. Disable with GROK_BOT_NO_AUTO_UPDATE=1 or
install.sh --no-auto-update.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --auto) AUTO=1; shift ;;
    --notify) NOTIFY=1; shift ;;
    --self-only) DO_APP=0; DO_DEPS=0; shift ;;
    --app-only) DO_SELF=0; DO_DEPS=0; shift ;;
    --deps-only) DO_SELF=0; DO_APP=0; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
export NOTIFY

if [[ "$AUTO" -eq 1 && -n "${GROK_BOT_NO_AUTO_UPDATE:-}" ]]; then
  exit 0
fi

mkdir -p "$CACHE_DIR"
LOG_FILE="$CACHE_DIR/update.log"

if [[ "$AUTO" -eq 1 ]]; then
  exec >>"$LOG_FILE" 2>&1
  echo
  info "auto-update $(date -Iseconds 2>/dev/null || date)"
  date +%s > "$CACHE_DIR/last-update-check"
fi

if ! mkdir "$CACHE_DIR/update.lock" 2>/dev/null; then
  if [[ "$AUTO" -eq 1 ]]; then
    info "another update is running; exiting"
    exit 0
  fi
  die "another update is already running"
fi
trap 'rmdir "$CACHE_DIR/update.lock" 2>/dev/null || true' EXIT

load_install_conf() {
  local conf="$ROOT/install.conf"
  if [[ -f "$conf" ]]; then
    # shellcheck disable=SC1090
    source "$conf"
  fi
  PREFIX="${PREFIX:-$HOME/.local}"
  if [[ "${SYSTEM:-0}" -eq 1 ]]; then
    OPT_DIR="${OPT_DIR:-${GROK_BOT_HOME:-/opt/Grok_Bot}}"
    BIN_DIR="${BIN_DIR:-$PREFIX/bin}"
    DATA_HOME="${DATA_HOME:-${XDG_DATA_HOME:-/usr/local/share}}"
    PACKAGING_DIR="${PACKAGING_DIR:-${GROK_BOT_LINUX_HOME:-/usr/local/opt/grok_bot_linux}}"
  else
    OPT_DIR="${OPT_DIR:-${GROK_BOT_HOME:-$PREFIX/opt/Grok_Bot}}"
    BIN_DIR="${BIN_DIR:-$PREFIX/bin}"
    DATA_HOME="${DATA_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}}"
    PACKAGING_DIR="${PACKAGING_DIR:-${GROK_BOT_LINUX_HOME:-$PREFIX/opt/grok_bot_linux}}"
  fi
}

write_install_conf() {
  mkdir -p "$PACKAGING_DIR"
  cat > "$PACKAGING_DIR/install.conf" <<EOF
PREFIX="$PREFIX"
OPT_DIR="$OPT_DIR"
BIN_DIR="$BIN_DIR"
DATA_HOME="$DATA_HOME"
SYSTEM="${SYSTEM:-0}"
PACKAGING_DIR="$PACKAGING_DIR"
EOF
}

reapply_icon() {
  local icon_src=""
  if [[ -f "$ROOT/share/grok-bot.png" ]]; then
    icon_src="$ROOT/share/grok-bot.png"
  elif [[ -f "$PACKAGING_DIR/share/grok-bot.png" ]]; then
    icon_src="$PACKAGING_DIR/share/grok-bot.png"
  fi
  [[ -n "$icon_src" ]] || return 0
  mkdir -p "$OPT_DIR"
  install -m 0644 "$icon_src" "$OPT_DIR/grok-bot.png" 2>/dev/null || cp -f "$icon_src" "$OPT_DIR/grok-bot.png"
  local size dir
  for size in 512 256; do
    dir="$DATA_HOME/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dir"
    install -m 0644 "$icon_src" "$dir/grok-bot.png" 2>/dev/null || cp -f "$icon_src" "$dir/grok-bot.png"
  done
}

refresh_launcher() {
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/grok-bot" <<EOF
#!/usr/bin/env bash
exec "$PACKAGING_DIR/launch.sh" "\$@"
EOF
  chmod 0755 "$BIN_DIR/grok-bot"
  ln -sfn "$BIN_DIR/grok-bot" "$BIN_DIR/grokbot"
  if [[ -f "$ROOT/share/grok-bot.desktop.in" ]]; then
    mkdir -p "$DATA_HOME/applications"
    sed -e "s|@BIN@|$BIN_DIR/grok-bot|" -e "s|@ICON@|grok-bot|" \
      "$ROOT/share/grok-bot.desktop.in" > "$DATA_HOME/applications/grok-bot.desktop"
    chmod 0644 "$DATA_HOME/applications/grok-bot.desktop"
  fi
}

reapply_sandbox() {
  local sandbox="$OPT_DIR/chrome-sandbox"
  [[ -f "$sandbox" ]] || return 0
  if sudo_n chown root:root "$sandbox" && sudo_n chmod 4755 "$sandbox"; then
    info "chrome-sandbox is setuid root"
  else
    warn "could not setuid chrome-sandbox (need passwordless sudo); launcher will use --no-sandbox"
  fi
}

apply_staged_app() {
  local next="$OPT_DIR.next"
  [[ -x "$next/grok-bot" && -f "$next/chrome_100_percent.pak" ]] || return 0
  if app_is_running "$OPT_DIR"; then
    warn "Grok Bot is still running; staged payload left at $next"
    return 0
  fi
  info "Applying staged Grok Bot at $next"
  rm -rf "$OPT_DIR.prev"
  if [[ -d "$OPT_DIR" ]]; then
    mv "$OPT_DIR" "$OPT_DIR.prev"
  fi
  mv "$next" "$OPT_DIR"
  reapply_icon
  reapply_sandbox
  rm -rf "$OPT_DIR.prev"
}

swap_app_dir() {
  local src="$1"
  if app_is_running "$OPT_DIR"; then
    info "Grok Bot is running; staging $src -> $OPT_DIR.next (applied on next launch)"
    rm -rf "$OPT_DIR.next"
    mv "$src" "$OPT_DIR.next"
    STAGED_APP=1
    return 0
  fi
  rm -rf "$OPT_DIR.prev"
  if [[ -d "$OPT_DIR" ]]; then
    mv "$OPT_DIR" "$OPT_DIR.prev"
  fi
  mv "$src" "$OPT_DIR"
  reapply_icon
  reapply_sandbox
  rm -rf "$OPT_DIR.prev"
}

check_wrapper() {
  WRAPPER_LOCAL="$(wrapper_revision "$ROOT")"
  WRAPPER_REMOTE="$(latest_wrapper_sha)" || return 1
  [[ -n "$WRAPPER_REMOTE" ]] || return 1
  if [[ "$FORCE" -eq 1 ]]; then
    WRAPPER_NEED=1
  elif [[ "$WRAPPER_LOCAL" == "unknown" || "$WRAPPER_LOCAL" != "$WRAPPER_REMOTE" ]]; then
    WRAPPER_NEED=1
  else
    WRAPPER_NEED=0
  fi
}

check_app() {
  APP_LOCAL="$(installed_app_version "$OPT_DIR")"
  local rel
  rel="$(latest_upstream_release)" || return 1
  APP_REMOTE="${rel%%$'\t'*}"
  local rest="${rel#*$'\t'}"
  APP_REMOTE_URL="${rest%%$'\t'*}"
  APP_REMOTE_SHA="${rest#*$'\t'}"
  [[ -n "$APP_REMOTE" && -n "$APP_REMOTE_URL" ]] || return 1
  if [[ "$FORCE" -eq 1 ]]; then
    APP_NEED=1
  elif ver_gt "$APP_REMOTE" "$APP_LOCAL"; then
    APP_NEED=1
  else
    APP_NEED=0
  fi
}

update_wrapper() {
  [[ "$DO_SELF" -eq 1 ]] || return 0
  [[ "$WRAPPER_NEED" -eq 1 ]] || { info "grok_bot_linux is up to date (${WRAPPER_LOCAL:0:12})"; return 0; }

  info "Updating grok_bot_linux ${WRAPPER_LOCAL:0:12} -> ${WRAPPER_REMOTE:0:12}"

  # If we are running out of PACKAGING_DIR, hop to a temp copy so we can
  # replace those files without truncating this script.
  if [[ -z "${GROK_BOT_UPDATE_INNER:-}" \
     && "$(readlink -f "$ROOT")" == "$(readlink -f "$PACKAGING_DIR")" ]]; then
    local inner
    inner="$(mktemp "${TMPDIR:-/tmp}/grok-bot-update.XXXXXX")"
    cp "$0" "$inner"
    chmod 0700 "$inner"
    export GROK_BOT_UPDATE_INNER=1 ROOT PACKAGING_DIR PREFIX OPT_DIR BIN_DIR DATA_HOME SYSTEM
    rmdir "$CACHE_DIR/update.lock" 2>/dev/null || true
    exec bash "$inner" "${ORIG_ARGS[@]}"
  fi

  local src="" tmp=""
  if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [[ -z "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]]; then
      git -C "$ROOT" fetch --quiet origin 2>/dev/null || true
      if git -C "$ROOT" merge --ff-only --quiet origin/main 2>/dev/null; then
        info "git fast-forwarded $ROOT"
        src="$ROOT"
      else
        warn "git merge --ff-only failed; installing GitHub main into $PACKAGING_DIR"
      fi
    else
      warn "$ROOT has local changes; not touching the git work tree"
    fi
  fi

  if [[ -z "$src" ]]; then
    tmp="$(mktemp -d)"
    http_download "$WRAPPER_TARBALL_URL" "$CACHE_DIR/grok_bot_linux-main.tar.gz"
    tar -xzf "$CACHE_DIR/grok_bot_linux-main.tar.gz" -C "$tmp"
    src="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -n1)"
  fi
  [[ -n "$src" && -f "$src/launch.sh" ]] || die "could not find grok_bot_linux files to install"

  mkdir -p "$PACKAGING_DIR"
  local item
  if [[ "$(readlink -f "$src")" != "$(readlink -f "$PACKAGING_DIR")" ]]; then
    for item in install.sh uninstall.sh launch.sh VERSION Makefile README.md LICENSE scripts share docker; do
      if [[ -e "$src/$item" ]]; then
        rm -rf "$PACKAGING_DIR/$item"
        cp -a "$src/$item" "$PACKAGING_DIR/$item"
      fi
    done
  fi
  printf '%s\n' "$WRAPPER_REMOTE" > "$PACKAGING_DIR/.wrapper-revision"
  write_install_conf
  chmod 0755 "$PACKAGING_DIR/install.sh" "$PACKAGING_DIR/uninstall.sh" "$PACKAGING_DIR/launch.sh" \
    "$PACKAGING_DIR/scripts/"*.sh 2>/dev/null || true
  refresh_launcher
  reapply_icon
  [[ -n "$tmp" ]] && rm -rf "$tmp"
  UPDATED_SELF=1

  if [[ -x "$PACKAGING_DIR/scripts/update.sh" ]]; then
    info "re-executing updated updater"
    rmdir "$CACHE_DIR/update.lock" 2>/dev/null || true
    exec "$PACKAGING_DIR/scripts/update.sh" "${ORIG_ARGS[@]}"
  fi
}

update_app() {
  [[ "$DO_APP" -eq 1 ]] || return 0
  [[ "$APP_NEED" -eq 1 ]] || { info "Grok Bot is up to date ($APP_LOCAL)"; return 0; }

  info "Updating Grok Bot $APP_LOCAL -> $APP_REMOTE"
  set_upstream_version "$APP_REMOTE"
  [[ -n "$APP_REMOTE_URL" ]] && UPSTREAM_URL="$APP_REMOTE_URL"
  [[ -n "$APP_REMOTE_SHA" ]] && UPSTREAM_SHA256="$APP_REMOTE_SHA"

  local dest dl
  dest="$(mktemp -d "$CACHE_DIR/app-XXXXXX")"
  dl="$PACKAGING_DIR/scripts/download-app.sh"
  [[ -x "$dl" ]] || dl="$ROOT/scripts/download-app.sh"
  "$dl" --force --skip-local --version "$APP_REMOTE" "$dest"
  printf '%s\n' "$APP_REMOTE" > "$dest/GROK_BOT_VERSION"
  printf '%s\n' "$APP_REMOTE" > "$PACKAGING_DIR/VERSION"
  if [[ "$(readlink -f "$ROOT")" != "$(readlink -f "$PACKAGING_DIR")" && -d "$ROOT" ]]; then
    printf '%s\n' "$APP_REMOTE" > "$ROOT/VERSION" 2>/dev/null || true
  fi
  swap_app_dir "$dest"
  UPDATED_APP=1
}

update_deps() {
  [[ "$DO_DEPS" -eq 1 ]] || return 0
  local deps="$PACKAGING_DIR/scripts/install-deps.sh"
  [[ -x "$deps" ]] || deps="$ROOT/scripts/install-deps.sh"
  [[ -x "$deps" ]] || return 0

  if [[ "$AUTO" -eq 1 ]]; then
    if sudo_n true; then
      info "Refreshing runtime packages"
      "$deps"
      UPDATED_DEPS=1
    else
      info "Skipping package refresh in auto mode (sudo would prompt)"
    fi
    return 0
  fi
  info "Refreshing runtime packages"
  "$deps"
  UPDATED_DEPS=1
}

summarize() {
  local parts=()
  [[ "${UPDATED_SELF:-0}" -eq 1 ]] && parts+=("Linux package")
  [[ "${UPDATED_APP:-0}" -eq 1 ]] && parts+=("Grok Bot $APP_REMOTE")
  [[ "${STAGED_APP:-0}" -eq 1 ]] && parts+=("Grok Bot $APP_REMOTE (next launch)")
  [[ "${UPDATED_DEPS:-0}" -eq 1 ]] && parts+=("runtime packages")
  if [[ ${#parts[@]} -eq 0 ]]; then
    info "Everything is up to date"
    notify_user "Grok Bot is up to date ($APP_LOCAL)"
  else
    local msg
    msg=$(IFS=', '; echo "${parts[*]}")
    info "Updated: $msg"
    notify_user "Updated: $msg"
  fi
}

load_install_conf
ORIG_ARGS=()
[[ "$CHECK_ONLY" -eq 1 ]] && ORIG_ARGS+=(--check)
[[ "$AUTO" -eq 1 ]] && ORIG_ARGS+=(--auto)
[[ "$NOTIFY" -eq 1 ]] && ORIG_ARGS+=(--notify)
[[ "$DO_SELF" -eq 1 && "$DO_APP" -eq 0 ]] && ORIG_ARGS+=(--self-only)
[[ "$DO_APP" -eq 1 && "$DO_SELF" -eq 0 ]] && ORIG_ARGS+=(--app-only)
[[ "$DO_DEPS" -eq 1 && "$DO_SELF" -eq 0 && "$DO_APP" -eq 0 ]] && ORIG_ARGS+=(--deps-only)
[[ "$FORCE" -eq 1 ]] && ORIG_ARGS+=(--force)

UPDATED_SELF=0
UPDATED_APP=0
UPDATED_DEPS=0
STAGED_APP=0
WRAPPER_NEED=0
APP_NEED=0
WRAPPER_LOCAL="unknown"
WRAPPER_REMOTE="unknown"
APP_LOCAL="$(installed_app_version "$OPT_DIR")"
APP_REMOTE="$APP_LOCAL"
APP_REMOTE_URL=""
APP_REMOTE_SHA=""

apply_staged_app || true

if [[ "$DO_SELF" -eq 1 ]]; then
  if ! check_wrapper; then
    if [[ "$AUTO" -eq 1 ]]; then
      warn "could not query latest grok_bot_linux; skipping self-update"
      WRAPPER_NEED=0
    else
      die "could not query latest grok_bot_linux from GitHub"
    fi
  fi
fi
if [[ "$DO_APP" -eq 1 ]]; then
  if ! check_app; then
    if [[ "$AUTO" -eq 1 ]]; then
      warn "could not query latest Grok Bot; skipping app update"
      APP_NEED=0
    else
      die "could not query latest Grok Bot from GitHub"
    fi
  fi
fi

if [[ "$CHECK_ONLY" -eq 1 ]]; then
  echo "grok_bot_linux  local=${WRAPPER_LOCAL:0:12}  latest=${WRAPPER_REMOTE:0:12}  $([[ "$WRAPPER_NEED" -eq 1 ]] && echo UPDATE || echo ok)"
  echo "Grok Bot        local=$APP_LOCAL  latest=$APP_REMOTE  $([[ "$APP_NEED" -eq 1 ]] && echo UPDATE || echo ok)"
  echo "dependencies    refresh on update (apt/dnf/pacman)"
  if [[ "$WRAPPER_NEED" -eq 1 || "$APP_NEED" -eq 1 ]]; then
    exit 2
  fi
  exit 0
fi

update_wrapper
# After a self-update, re-read VERSION/helpers if we did not re-exec.
if [[ "$DO_APP" -eq 1 ]]; then
  # Recheck against (possibly new) helper copy.
  if [[ -f "$PACKAGING_DIR/scripts/common.sh" ]]; then
    # shellcheck disable=SC1091
    ROOT="$PACKAGING_DIR" source "$PACKAGING_DIR/scripts/common.sh"
    load_install_conf
    check_app
  fi
fi
update_app
update_deps
summarize
