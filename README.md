# Grok Bot Linux

Stand-alone Linux package for the official Grok Bot desktop app. It installs
runtime libraries, the Electron app, a desktop launcher, optional Docker, and
the Ivy Bridge VA-API fix so Chromium does not fail on `iHD_drv_video.so`.

Grok Bot has no official Linux build. The app payload comes from the community
[Linux port](https://github.com/Nichokas/grokbot-linux-port) of Grok Bot
**0.24.0** (Electron 42.1.0).

## Download and install

From the stand-alone archive:

```bash
tar -xzf grok_bot_linux-0.24.0-linux-x64.tar.gz
cd grok_bot_linux-0.24.0-linux-x64
./install.sh --with-docker
grok-bot
```

`./install.sh` will:

- Install GTK/NSS/ALSA/VA-API packages and Unicode fonts (Noto, CJK, emoji)
- Run Grok Bot under a UTF-8 locale so non-ASCII text renders and copies correctly
- Optionally install Docker Engine + Compose (`--with-docker`)
- Unpack Grok Bot into `~/.local/opt/Grok_Bot`
- Install `~/.local/bin/grok-bot` and a desktop entry
- Set `chrome-sandbox` setuid root when sudo is available
- Force `LIBVA_DRIVER_NAME=i965` on Intel Gen6–Gen7.5 GPUs (HD Graphics 4000)

### Installer flags

| Flag | Effect |
| --- | --- |
| `--with-docker` | Install `docker.io`, `docker-cli`, `docker-compose`, `containerd` |
| `--prefix DIR` | Install prefix (default `~/.local`) |
| `--system` | Install to `/usr/local` + `/opt/Grok_Bot` |
| `--skip-deps` | Skip OS package install |
| `--download` | Re-fetch the app tarball |
| `--no-sandbox-ok` | Skip setuid on `chrome-sandbox` |
| `--no-auto-update` | Skip the daily systemd update timer |

Uninstall:

```bash
./uninstall.sh
```

User data in `~/.grokbot` and `~/.config/Grok Bot` is left in place.

## Updates

`grok-bot update` refreshes three things when a newer version exists:

1. **This Linux package** (`code4johnm/grok_bot_linux` on GitHub) — launcher, icon, scripts
2. **Grok Bot** — the Electron app from [Nichokas/grokbot-linux-port](https://github.com/Nichokas/grokbot-linux-port/releases)
3. **Runtime packages** — GTK, NSS, VA-API, and the other libraries `install-deps.sh` manages

```bash
grok-bot update              # apply whatever is newer
grok-bot update --check      # report only
grok-bot update --app-only   # Electron payload
grok-bot update --self-only  # launcher / packaging
grok-bot update --deps-only  # OS packages (needs sudo)
make update
```

If Grok Bot is running, the new app is staged and swapped in on the next launch instead of overwriting a live process.

Automatic updates run:

- Daily via a systemd user timer (`grok-bot-update.timer`)
- At most once per day when you start `grok-bot`

Turn them off with `GROK_BOT_NO_AUTO_UPDATE=1`, or install with `./install.sh --no-auto-update`. Logs: `~/.cache/grok-bot/update.log`.

## Docker

The image has the Electron runtime, Intel VA-API drivers, and an X11-forwarding
compose file. The host app directory is mounted at `/opt/Grok_Bot`.

```bash
./install.sh --with-docker          # once; then log out/in so docker group applies
xhost +local:docker                 # allow the container to use your display
docker compose -f docker/docker-compose.yml up --build
```

The container always passes `--no-sandbox` (Chromium's SUID sandbox is not used
inside Docker). GPU devices (`/dev/dri`) are passed through.

To bake the app into an image tarball as well:

```bash
./scripts/build-package.sh --with-docker-image
# produces dist/grok_bot_linux-0.24.0-docker.tar.gz
docker load < dist/grok_bot_linux-0.24.0-docker.tar.gz
```

## Build the downloadable archive

On a machine that already has Grok Bot (or network access to GitHub Releases):

```bash
./scripts/build-package.sh
ls dist/grok_bot_linux-0.24.0-linux-x64.tar.gz dist/SHA256SUMS
```

The archive includes `app/` (the Electron tree), `install.sh`, Docker files, and
this README. Recipients do not need GitHub if they use that tarball.

## What was fixed on launch

On Intel Ivy Bridge HD Graphics 4000, Electron probes `iHD` (Gen8+) first and
prints:

```text
libva error: /usr/lib/x86_64-linux-gnu/dri/iHD_drv_video.so init failed
```

`launch.sh` detects pre-Broadwell Intel GPUs and sets `LIBVA_DRIVER_NAME=i965`.
Override with `LIBVA_DRIVER_NAME=... grok-bot` if needed.

If `LANG` is not a UTF-8 locale, the launcher sets `C.UTF-8` (or `en_US.UTF-8`)
so Chromium can display CJK, emoji, and other Unicode text. Install Noto fonts
with `./scripts/install-deps.sh` or `grok-bot update --deps-only`.

## Layout

```text
install.sh / uninstall.sh / launch.sh
scripts/install-deps.sh      GTK, NSS, ALSA, libva, Noto/CJK/emoji fonts
scripts/install-docker.sh    docker.io, compose, containerd, docker group
scripts/download-app.sh      bundle or fetch Grok_Bot_<ver>_linux_x64.tar.gz
scripts/update.sh            wrapper + app + OS package updates
scripts/build-package.sh     dist/*.tar.gz
docker/Dockerfile            debian:bookworm-slim + Electron deps
docker/docker-compose.yml    X11 + /dev/dri
share/grok-bot.desktop.in
app/                         Electron payload (filled by install/build)
```

## License

Packaging scripts are MIT (see `LICENSE`). Grok Bot itself is proprietary.
