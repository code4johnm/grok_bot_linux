#!/usr/bin/env bash
# Install the official Grok / Grok Build CLI (native Linux).
# Uses https://x.ai/cli/install.sh — never prints credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/common.sh
source "$ROOT/scripts/common.sh"

FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

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
