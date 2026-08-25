# Grok Bot Linux (Ubuntu LTS + Rocky Linux + Kali)

Stand-alone packaging for **two** products on **three first-class OS
targets** (x86_64):

| Role | OS | Installer |
| --- | --- | --- |
| Primary desktop / common | **Ubuntu LTS** 24.04 / 26.04 | `scripts/install-ubuntu.sh` |
| Primary enterprise / RHEL-family | **Rocky Linux** 9 or 10 | `scripts/install-rocky.sh` |
| Primary Debian-family rolling | **Kali Linux** | `scripts/install-kali.sh` |
| Ubuntu cousins | Debian, Linux Mint | `install-ubuntu.sh` |
| Rocky cousins | RHEL, AlmaLinux | `install-rocky.sh` |
| Notes only | Fedora | — |

**Install prefix on every dist (system):** `/opt/grok-bot`  
Plus `/usr/local/bin/grok-bot` and `/usr/share/applications/grok-bot.desktop`.

Do not treat Rocky as “Ubuntu with dnf”. Do not treat Kali as an unnamed
Ubuntu cousin — it has its own installer. Package names, SELinux, and
sandbox rules stay on the matching script.

| Product | What it is | How it is installed |
| --- | --- | --- |
| **Grok Bot desktop** | Official teammate / virtual-computer GUI from https://x.ai/bot | Community Linux port (no official vendor `.deb`) |
| **Grok CLI** | Official native Linux agent / Grok Build | `curl -fsSL https://x.ai/cli/install.sh \| bash` |
| **grok-bot-tui** | Companion TUI around **Grok Bot** (not Grok at grok.com). `/gui` → packaged `grok-bot` or https://x.ai/bot. Default action is the official `grok` CLI (Grok Build TUI). | `pip install -e ./grok-bot-tui` — see [grok-bot-tui/README.md](grok-bot-tui/README.md) |

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

## UBUNTU (copy-paste)

Ubuntu 26.04 LTS or 24.04 LTS, x86_64. Substitute your actual clone path.

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates git tar
git clone <this-repository> grok_bot_linux
cd grok_bot_linux
sudo ./scripts/install-ubuntu.sh --system --with-cli
# or: ./scripts/install-for.sh ubuntu --system --with-cli
grok-bot
grok --version
```

Non-root:

```bash
./scripts/install-ubuntu.sh --user --with-cli
export PATH="$HOME/.local/bin:$HOME/.grok/bin:$PATH"
grok-bot
grok --version
```

## ROCKY (copy-paste)

Rocky Linux 9 or 10, x86_64. Same app prefix as Ubuntu: `/opt/grok-bot`.

```bash
sudo dnf install -y curl ca-certificates git tar
git clone <this-repository> grok_bot_linux
cd grok_bot_linux
sudo ./scripts/install-rocky.sh --system --with-cli
# or: ./scripts/install-for.sh rocky --system --with-cli
grok-bot
grok --version
ldd /opt/grok-bot/grok-bot | grep "not found" || true
```

Non-root:

```bash
./scripts/install-rocky.sh --user --with-cli
export PATH="$HOME/.local/bin:$HOME/.grok/bin:$PATH"
grok-bot
grok --version
```

Exact dnf runtime line (resolved by `scripts/install-deps.sh`; names are
Rocky/RHEL, not Debian):

```bash
sudo dnf install -y gtk3 libnotify nss libXScrnSaver libXtst xdg-utils \
  mesa-libgbm alsa-lib at-spi2-atk at-spi2-core libdrm libxkbcommon \
  cups-libs libXcomposite libXdamage libXrandr libXfixes libsecret \
  vulkan-loader libva liberation-fonts
```

## KALI (copy-paste)

Kali Linux x86_64 (Debian/rolling, **not Ubuntu**). Desktop is often XFCE on
X11. System prefix: `/opt/grok-bot`. Does not install offensive Kali tools.

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates git tar
git clone <this-repository> grok_bot_linux
cd grok_bot_linux
sudo ./scripts/install-kali.sh --system --with-cli
# or: ./scripts/install-for.sh kali --system --with-cli
grok-bot
grok --version
echo "session=${XDG_SESSION_TYPE:-unknown}"
```

Non-root (docs still prefer `/opt/grok-bot` with `--system`):

```bash
./scripts/install-kali.sh --user --with-cli
export PATH="$HOME/.local/bin:$HOME/.grok/bin:$PATH"
grok-bot
grok --version
```

Do not live as root. If the installer is run with sudo, launch `grok-bot` as
a normal user.

**Debian / Mint:** `./scripts/install-ubuntu.sh`.

Optional packages:

```bash
./scripts/build-deb.sh    # Ubuntu/Debian amd64
./scripts/build-rpm.sh    # Rocky/RHEL x86_64
sudo apt install ./dist/grok-bot_0.24.0_amd64.deb
sudo dnf install ./dist/grok-bot-0.24.0-1.*.rpm
```

Do **not** install the macOS `.dmg` in Docker as a Linux implementation.

## Ubuntu vs Rocky vs Kali

| Item | Ubuntu LTS | Rocky Linux 9/10 | Kali Linux |
| --- | --- | --- | --- |
| Installer | `scripts/install-ubuntu.sh` | `scripts/install-rocky.sh` | `scripts/install-kali.sh` |
| Packages | apt | dnf | apt |
| Desktop | do not assume; GNOME common | do not assume | XFCE common, do not assume GNOME |
| App prefix | `/opt/grok-bot` | `/opt/grok-bot` | `/opt/grok-bot` |
| CLI | official `install.sh` | official `install.sh` | official `install.sh` |
| Artifact | `.deb` | `.rpm` | `.deb` |
| Hardening | AppArmor / userns | SELinux / userns | sandbox + rolling-lib drift |
| Fallback | `grok-bot --no-sandbox` | `grok-bot --no-sandbox` | `grok-bot --no-sandbox` |

Kali is Debian/rolling, **not Ubuntu**. Probe classic Debian names with
`apt-cache policy`, then install the first name that has a Candidate.

**Kali package mapping** (classic Debian name → name that apt can install on
current Kali rolling; recorded from `apt-cache policy`):

| Debian / docs name | Kali rolling equivalent |
| --- | --- |
| `libgtk-3-0` | `libgtk-3-0t64` |
| `libasound2` | `libasound2t64` |
| `libatk-bridge2.0-0` | `libatk-bridge2.0-0t64` |
| `libatspi2.0-0` | `libatspi2.0-0t64` |
| `libcups2` | `libcups2t64` |
| `libfuse2` | none (optional; tarball does not need it) |
| `libnotify4` `libnss3` `libxss1` `libxtst6` `xdg-utils` `libgbm1` `libdrm2` `libxkbcommon0` | same name |

**Kali chrome-sandbox**

```bash
sudo chown root:root /opt/grok-bot/chrome-sandbox
sudo chmod 4755 /opt/grok-bot/chrome-sandbox
grok-bot
# if it fails (userns / AppArmor / rolling-lib drift):
GROK_BOT_NO_SANDBOX=1 grok-bot
```

Do not operate the GUI as root. Check `$XDG_SESSION_TYPE` (`x11` is typical
on XFCE; if `wayland`, try `ELECTRON_OZONE_PLATFORM_HINT=x11`).

Rocky is not Ubuntu. Do not pass Debian names (`libgtk-3-0`, `libasound2`) to
`dnf`. `gtk3` and `alsa-lib` are the Rocky names.

**SELinux (Rocky).** Check `getenforce`. If `Enforcing`, the installer runs
`restorecon -Rv /opt/grok-bot`. It will **not** run `setenforce 0`. If
`chrome-sandbox` still fails:

```bash
sudo ausearch -m avc -ts recent
# then, as a documented fallback only:
GROK_BOT_NO_SANDBOX=1 grok-bot
```

Do not open firewalld ports. Login uses outbound HTTPS; browser callbacks
are localhost (no extra ports).

**Verify on Rocky**

```bash
grok --version
grok-bot --version || true
ldd /opt/grok-bot/grok-bot | grep "not found" || true
cat /opt/grok-bot/.sandbox-path 2>/dev/null || true
getenforce
```

**Common Rocky failures**

- missing `nss` / `gtk3` — `./scripts/install-deps.sh`
- `chrome-sandbox` setuid ignored — userns or SELinux; use `--no-sandbox` fallback
- SELinux AVC on `/opt/grok-bot` — `restorecon -Rv /opt/grok-bot`, then ausearch
- Wayland on recent Rocky spins — `ELECTRON_OZONE_PLATFORM_HINT=x11 grok-bot`
- old NVIDIA/GBM — update mesa/`mesa-libgbm`, or run on X11

**CLI PATH on Rocky** (desktop sessions often skip `.profile`):

- `$HOME/.bashrc` and `$HOME/.profile` (always)
- `$HOME/.config/environment.d/grok.conf` (systemd user environment)
- `/etc/profile.d/grok.sh` when installing `--system --with-cli`

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
./scripts/uninstall.sh
./scripts/uninstall-rocky.sh   # Rocky: also drops /etc/profile.d/grok.sh
sudo apt remove grok-bot       # .deb
sudo dnf remove grok-bot       # .rpm
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
If the kernel disables them, setuid `chrome-sandbox` is required. Ubuntu:
do not disable AppArmor globally. Rocky: do not `setenforce 0`. Use
`--no-sandbox` only as a fallback. The launcher writes `suid` or
`no-sandbox` to `/opt/grok-bot/.sandbox-path`.

**Tofu / missing CJK or emoji**
The launcher forces a UTF-8 locale when `LANG` is `C`/`POSIX`. Install Noto
fonts via `./scripts/install-deps.sh`.

**Intel Ivy Bridge (`iHD_drv_video.so` init failed)**
The launcher sets `LIBVA_DRIVER_NAME=i965` on Gen6–Gen7.5 GPUs.

**arm64 desktop**
Not available from the community port. Use the official CLI on aarch64.

## For other agents

Canonical path other agents should call:

```text
Install Grok Bot for ubuntu|rocky|kali

./scripts/install-for.sh ubuntu --system --with-cli
./scripts/install-for.sh rocky  --system --with-cli
./scripts/install-for.sh kali   --system --with-cli
./scripts/install-for.sh auto   --system --with-cli
```

Detection (`auto`): `/etc/os-release` — kali (`ID` or `ID_LIKE`) first, then
ubuntu/debian/linuxmint, then rocky/rhel/centos. Prefix: `/opt/grok-bot`.

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
