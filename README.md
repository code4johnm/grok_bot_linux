# Grok Bot Linux (Ubuntu LTS)

Stand-alone packaging for **two** products on Ubuntu LTS (x86_64) and other
Debian-family systems (Debian, Linux Mint, Kali):

| Product | What it is | How it is installed |
| --- | --- | --- |
| **Grok Bot desktop** | Official teammate / virtual-computer GUI from https://x.ai/bot | Community Linux port (no official vendor `.deb`) |
| **Grok CLI** | Official native Linux agent / Grok Build | `curl -fsSL https://x.ai/cli/install.sh \| bash` |

The desktop app is a GUI around the same ecosystem. It does **not** replace the
CLI. Install both.

**Official support status.** xAI/Cursor do not currently ship a native Linux
`.deb` or `.rpm` for Grok Bot desktop. This tree uses the public
[community Linux port](https://github.com/Nichokas/grokbot-linux-port) of the
official Windows package fused with Electron for Linux. The CLI **is** official
and supports Linux x86_64 and arm64.

**Architecture.** Desktop: **x86_64 only**. CLI: x86_64 and aarch64. There is
no working Grok Bot desktop tarball for arm64 at this time.

Privacy: examples use `$HOME`, `/opt/grok-bot`, and `user@example.org` only.

## Ubuntu install (copy-paste)

On Ubuntu 26.04 LTS or 24.04 LTS (x86_64). Substitute your actual clone path.

System-wide (recommended; needs sudo once):

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates tar
git clone <this-repository> grok_bot_linux
cd grok_bot_linux
sudo ./scripts/install-ubuntu.sh --system --with-cli
grok-bot
grok --version
```

Non-root (no `/opt`; still a full desktop + CLI):

```bash
./scripts/install-ubuntu.sh --user --with-cli
export PATH="$HOME/.local/bin:$HOME/.grok/bin:$PATH"
grok-bot
grok --version
```

Debian, Linux Mint, and Kali: the same scripts. Package names with a `t64`
suffix (Ubuntu 24.04+) are selected automatically.

Optional `.deb` (amd64), if you built one on this tree:

```bash
./scripts/build-deb.sh
sudo apt install ./dist/grok-bot_0.24.0_amd64.deb
```

Do **not** install the macOS `.dmg` in Docker as a Linux implementation.

## Layout

System install (`--system`):

```text
/opt/grok-bot/                 Electron app + icon.png
/usr/local/bin/grok-bot        launcher
/usr/share/applications/grok-bot.desktop
/usr/lib/grok-bot-linux/       packaging scripts
$HOME/.config/Grok Bot/        app user data (vendor path)
$HOME/.grokbot/                extra app data
$HOME/.grok/bin/grok           official CLI
```

User install (`--user`):

```text
$HOME/.local/opt/grok-bot/
$HOME/.local/bin/grok-bot
$HOME/.local/share/applications/grok-bot.desktop
```

## Official CLI

```bash
./scripts/install-cli.sh
# or:
curl -fsSL https://x.ai/cli/install.sh | bash
export PATH="$HOME/.grok/bin:$PATH"
grok --version
```

The helper also appends `$HOME/.grok/bin` to `~/.bashrc` and `~/.profile`.

First-run login (interactive; do not paste tokens into chat or git):

```bash
grok
# or
grok login
```

Optional environment (never commit the value):

```bash
export XAI_API_KEY="[secret redacted]"
```

Update:

```bash
grok update
grok update --check
```

## Desktop launcher

Menu name: **Grok Bot**. File: `grok-bot.desktop`.

```bash
grok-bot                 # start
grok-bot update          # wrapper + app + OS packages
grok-bot update --check
grok-bot --version
```

Right-click the menu entry → **Update Grok Bot**.

## Sandbox (`chrome-sandbox`)

Chromium’s SUID sandbox is the default when it can be enabled:

```bash
sudo chown root:root /opt/grok-bot/chrome-sandbox
sudo chmod 4755 /opt/grok-bot/chrome-sandbox
```

If AppArmor, user namespaces, or missing sudo block that, the launcher falls
back to `--no-sandbox` and logs a warning.

| Mode | When | Tradeoff |
| --- | --- | --- |
| Sandbox on (SUID `chrome-sandbox`) | Default after a successful setuid | Isolates renderer processes |
| `--no-sandbox` | Docker, unprivileged userns, or setuid failed | Weaker isolation; app still runs |

Force the fallback: `GROK_BOT_NO_SANDBOX=1 grok-bot` or install with
`--no-sandbox-ok`.

Ubuntu `kernel.unprivileged_userns_clone=0` also blocks the sandbox. Prefer
fixing setuid rather than leaving `--no-sandbox` on a daily driver.

## Updates

Desktop tarball SHA256 is verified against the GitHub release digest when
present.

```bash
grok-bot update              # this package + Grok Bot + runtime libs
grok-bot update --app-only
grok-bot update --self-only
grok-bot update --deps-only  # needs sudo
grok update                  # official CLI
```

Auto: systemd user timer `grok-bot-update.timer` (daily) and at most one check
per day on launch. Disable with `GROK_BOT_NO_AUTO_UPDATE=1` or
`--no-auto-update`.

If the GUI is running, a new app is staged and swapped in on the next launch.

## Uninstall

```bash
./uninstall.sh
# or
./scripts/uninstall.sh
sudo apt remove grok-bot     # if installed from the .deb
```

User data in `$HOME/.grokbot`, `$HOME/.config/Grok Bot`, `$HOME/.grok`, and
`$HOME/.cache/grok-bot` is left in place.

## Troubleshooting

**`grok-bot: command not found`**
Add the bin dir: `export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"`.

**`grok: command not found`**
`export PATH="$HOME/.grok/bin:$PATH"` then open a new terminal.

**`chrome-sandbox` permission / “No usable sandbox”**
Run the `chown`/`chmod` above, or start with `GROK_BOT_NO_SANDBOX=1 grok-bot`.

**Missing GTK / NSS / ALSA**
`./scripts/install-deps.sh` (needs sudo). On Ubuntu 24.04+ the `t64` package
names are used automatically.

**Wayland vs X11**
The launcher sets `ELECTRON_OZONE_PLATFORM_HINT=auto`. Force X11:
`GDK_BACKEND=x11 grok-bot` or `ELECTRON_OZONE_PLATFORM_HINT=x11 grok-bot`.

**Unprivileged user namespaces**
If the kernel disables them, setuid `chrome-sandbox` is required. Do not
disable AppArmor globally; use `--no-sandbox` only as a fallback.

**Tofu / missing CJK or emoji**
The launcher forces a UTF-8 locale when `LANG` is `C`/`POSIX`. Install Noto
fonts via `./scripts/install-deps.sh`.

**Intel Ivy Bridge (`iHD_drv_video.so` init failed)**
The launcher sets `LIBVA_DRIVER_NAME=i965` on Gen6–Gen7.5 GPUs.

**arm64 desktop**
Not available from the community port. Use the official CLI on aarch64.

## For other agents

Canonical Ubuntu LTS (x86_64) path other bots should call:

```text
./scripts/install-ubuntu.sh --system --with-cli
```

Non-root:

```text
./scripts/install-ubuntu.sh --user --with-cli
```

CLI only:

```text
./scripts/install-cli.sh
```

Do not wrap the macOS DMG. Do not scrape extra app bits beyond the public
Linux port. Do not embed credentials. Do not change sudoers without asking.

## Docker (optional)

X11 + `/dev/dri`. The container always uses `--no-sandbox`.

```bash
./install.sh --with-docker
xhost +local:docker
docker compose -f docker/docker-compose.yml up --build
```

## License

Packaging scripts are MIT (see `LICENSE`). Grok Bot itself is proprietary.
The official CLI is distributed by xAI under its own terms.
