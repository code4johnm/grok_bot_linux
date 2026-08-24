#!/usr/bin/env bash
# Install the official Grok / Grok Build CLI (native Linux).
# Uses https://x.ai/cli/install.sh — never prints credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

FORCE=0
SYSTEM_PROFILE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --system-profile) SYSTEM_PROFILE=1; shift ;;
    -h|--help)
      echo "Usage: $0 [--force] [--system-profile]"
      exit 0
      ;;
    *) die "unknown option: $1" ;;
  esac
done

CLI_BIN="${GROK_BIN_DIR:-$HOME/.grok/bin}"
OFFICIAL_INSTALLER="https://x.ai/cli/install.sh"

ensure_path_block() {
  local block file
  block='# >>> grok installer >>>
export PATH="$HOME/.grok/bin:$PATH"
[[ -r "$HOME/.grok/completions/bash/grok.bash" ]] && source "$HOME/.grok/completions/bash/grok.bash"
# <<< grok installer <<<'
  for file in "$HOME/.bashrc" "$HOME/.profile"; do
    mkdir -p "$(dirname "$file")"
    touch "$file"
    if grep -qs "grok installer" "$file" 2>/dev/null; then
      continue
    fi
    printf '\n%s\n' "$block" >> "$file"
    info "Added \$HOME/.grok/bin to PATH in $(basename "$file")"
  done
}

if [[ "$FORCE" -eq 0 ]] && have grok; then
  info "Official Grok CLI already on PATH"
else
  info "Installing official Grok CLI"
  have curl || die "curl is required to install the Grok CLI"
  curl -fsSL "$OFFICIAL_INSTALLER" | bash
fi

ensure_path_block

# Desktop (non-login) sessions on systemd: $HOME/.config/environment.d
env_dir="${XDG_CONFIG_HOME:-$HOME/.config}/environment.d"
mkdir -p "$env_dir"
if [[ ! -f "$env_dir/grok.conf" ]]; then
  printf 'PATH=%%h/.grok/bin:/usr/local/bin:/usr/bin:/bin\n' > "$env_dir/grok.conf"
  info "Wrote \$HOME/.config/environment.d/grok.conf (re-login for GUI apps)"
fi

if [[ "$SYSTEM_PROFILE" -eq 1 ]]; then
  if is_root; then
    cat > /etc/profile.d/grok.sh <<'EOF'
# Official Grok CLI (per-user). Adds $HOME/.grok/bin when present.
# Does not change sudoers. Outbound HTTPS only; no firewalld ports.
if [ -d "$HOME/.grok/bin" ]; then
  case ":$PATH:" in
    *":$HOME/.grok/bin:"*) ;;
    *) PATH="$HOME/.grok/bin:$PATH" ;;
  esac
  export PATH
fi
EOF
    chmod 0644 /etc/profile.d/grok.sh
    info "Wrote /etc/profile.d/grok.sh"
  else
    warn "skipping /etc/profile.d/grok.sh (not root)"
  fi
fi

# Current session
case ":$PATH:" in
  *":$CLI_BIN:"*) ;;
  *) export PATH="$CLI_BIN:$PATH" ;;
esac

if have grok; then
  info "CLI: $(grok --version 2>/dev/null | head -n1 || echo grok)"
  log "Login (do not paste keys into chat):  grok login"
  log "Optional env (never commit this):     export XAI_API_KEY=\"[secret redacted]\""
else
  warn "grok not on PATH in this shell. Open a new terminal or run:"
  log "  export PATH=\"\$HOME/.grok/bin:\$PATH\""
fi
