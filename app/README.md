This directory holds the Grok Bot Electron tree (`grok-bot`, `chrome-sandbox`, `resources/`, …).

`./install.sh` and `./scripts/build-package.sh` populate it from:

1. A copy already at `$HOME/.local/opt/grok-bot` (or `$HOME/.local/opt/Grok_Bot`), or
2. The community Linux tarball (`Grok_Bot_<ver>_linux_x64.tar.gz` or
   `Grok_Bot_<ver>_linux_arm64.tar.gz`), a verbatim extract of the official
   vendor `.deb`.
