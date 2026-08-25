# Grok GUI TUI shell (`grok-tui-shell`)

Companion **terminal** client for **Grok Bot**, the Electron desktop app
packaged in this repository. Footer and title chrome: `Grok GUI TUI shell`.

**This is not Grok.** It is not a rebrand of Grok Bot, not grok.com chat, and
not the official `grok` CLI (`curl -fsSL https://x.ai/cli/install.sh | bash`).

| Name | Role |
| --- | --- |
| **Grok Bot** (`grok-bot`) | Electron GUI. Teammate / virtual-computer product from https://x.ai/bot. Signs in with Cursor SSO (Gmail and other IdPs). |
| **`grok-tui-shell`** | Fullscreen TUI around that GUI: same sign-in, same bot roster, keyboard navigation. Commands `grok-tui-shell` and `grok-bot-tui` are aliases. |
| **`grok` CLI** | Separate official product. Device/OIDC at `accounts.x.ai`. This shell does **not** call `grok login`. |

Package: `grok-bot-tui` 0.4.0. Python 3.9+ (Pi 3 Bookworm / Ubuntu 20.04+).
License: MIT (this packaging tree). Targets: Ubuntu, Kali Linux, Rocky Linux,
and Raspberry Pi OS / Ubuntu on Raspberry Pi (x86_64, aarch64, armv7l).

## Contents

1. [What it does](#what-it-does)
2. [What it does not do](#what-it-does-not-do)
3. [Requirements](#requirements)
4. [Install](#install)
5. [Raspberry Pi](#raspberry-pi)
6. [Auto-start / boot](#auto-start--boot)
7. [Run](#run)
8. [Non-interactive CLI](#non-interactive-cli)
9. [Screen layout](#screen-layout)
10. [Sign-in (same as Grok Bot)](#sign-in-same-as-grok-bot)
11. [Bot list](#bot-list)
12. [Keys and commands](#keys-and-commands)
13. [Talking to a bot](#talking-to-a-bot)
14. [Optional api.x.ai chat](#optional-apixai-chat)
15. [Launching the desktop app](#launching-the-desktop-app)
16. [CLI flags](#cli-flags)
17. [Environment](#environment)
18. [Files and paths](#files-and-paths)
19. [Privacy](#privacy)
20. [Troubleshooting](#troubleshooting)
21. [Tests and development](#tests-and-development)

## What it does

- Fullscreen prompt_toolkit UI: header, body, `compose>` line, status footer.
- **Sign-in the same way as Grok Bot:** `/login` prints a clickable OSC 8 link
  to `https://cursor.com/bot/onboarding` and **launches `grok-bot`**. Finish
  Gmail / Cursor SSO in that window. The TUI does not ask for a Gmail password.
- Detects an existing GUI session so you do not sign in twice.
- After sign-in, lists **your** bots from the signed-in Grok Bot roster cache
  (names, unread counts, pin order, last selected). Heading:
  `Bots  (N from signed-in Grok Bot)`.
- One-row pixel sprites (`█░`) hashed from each bot id. Narrow terminals
  collapse to `[A]`.
- `j` / `k` or arrow keys move; Enter selects; typing a message opens Grok Bot
  so you assign the work in the GUI.

## What it does not do

- It is not Grok Bot. Work still runs in the desktop app.
- It does **not** implement a private Gmail OAuth client. Cursor SSO stays in
  grok-bot.
- It does **not** read Cookies, `sand-secrets.json`, gateway blobs, or tokens.
- It does **not** list public x.ai/bot marketing templates (Sales Outbound,
  Talent Scout, …) as if they were your session. If you still see those, you
  are on a stale install (0.3.0 or older). Reinstall and restart; header must
  show **0.4.0**.
- It does **not** call the official `grok` CLI or `grok login --device-auth`.
- It cannot list bots that grok-bot has never synced to disk. Open grok-bot
  once, then `/agents`.

## Requirements

| Item | Notes |
| --- | --- |
| Python | 3.9 or newer (3.11+ preferred) |
| Terminal | UTF-8 locale. OSC 8 hyperlinks work in VTE, Kitty, iTerm2, Windows Terminal, and similar. The raw URL is always printed too. SSH and headless Pi: use CLI commands or tmux. |
| Grok Bot desktop | Needed for Gmail/Cursor SSO and the roster. **x86_64 only.** Install with `./install.sh` or `scripts/install-ubuntu.sh` / `install-rocky.sh` / `install-kali.sh`. Prefix: `/opt/grok-bot` (system) or `$HOME/.local/opt/grok-bot` (user). |
| Raspberry Pi / ARM | TUI + CLI run on Pi 3/4/5 (`armv7l`, `aarch64`). No Electron grok-bot tarball; `/gui` and `/login` launch will say so. Use `grok-tui-shell status`. |

Python deps (from `pyproject.toml`): `httpx`, `prompt_toolkit`. Optional:
`pytest` (`[dev]`), `keyring` (API-key store only).

## Install

One installer detects Ubuntu, Kali, Rocky, and Raspberry Pi OS (apt or dnf;
x86_64 / aarch64 / armv7l). It does **not** install Electron grok-bot or any
Kali offensive metapackage. Default is a **user** install (do not live as
root on Kali or Pi).

```bash
# from this clone
./grok-bot-tui/install.sh --yes
# same: ./scripts/install-tui.sh --yes
# Raspberry Pi boot autostart (tmux + systemd --user):
./grok-bot-tui/install.sh --yes --autostart

export PATH="$HOME/.local/bin:$PATH"
grok-tui-shell status
```

Flags: `--user` (default), `--system` (root, `/usr/local`), `--autostart`,
`--yes`.

Editable install with tests:

```bash
python3 -m pip install --user -e "./grok-bot-tui[dev]"
```

`pip` registers `grok-tui-shell` and `grok-bot-tui` (aliases).

```bash
python3 -m pip show grok-bot-tui
# Version: 0.4.0
```

Install grok-bot itself on **x86_64** so `/login` can launch the GUI:

```bash
sudo ./scripts/install-ubuntu.sh --system   # or install-rocky.sh / install-kali.sh
```

## Raspberry Pi

Runs on **Raspberry Pi OS** (32-bit armv7l and 64-bit aarch64) and **Ubuntu
for Raspberry Pi**. Pi 3 / 4 / 5 are in scope. Keep the footprint small: the
installer only adds `python3`, `pip`, `venv`/`ca-certificates`, and optional
`tmux`.

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-pip python3-venv ca-certificates
git clone <this-repository> grok_bot_linux
cd grok_bot_linux
./grok-bot-tui/install.sh --yes --autostart
export PATH="$HOME/.local/bin:$PATH"
grok-tui-shell status
```

Notes:

- **No Electron grok-bot** on ARM. `/login` still prints
  `https://cursor.com/bot/onboarding`; complete Gmail on an x86_64 grok-bot
  box if you need the GUI roster. On the Pi, `whoami` / `bots` read local
  `$HOME/.config/Grok Bot/` if you copied a profile (not recommended) or
  stay signed out and use optional `XAI_API_KEY`.
- SSH is the normal UI: `ssh host` then `grok-tui-shell`.
- UTF-8 locale: `sudo dpkg-reconfigure locales` (en_US.UTF-8 is enough).
- Do not run as root. Use a login user + `loginctl enable-linger` for
  systemd --user.

## Auto-start / boot

Useful on a headless Pi. The unit starts a **tmux** session named `grok-tui`
so the TUI has a PTY (systemd cannot attach a fullscreen TUI to HDMI unless
you autologin to a getty).

```bash
./grok-bot-tui/install.sh --yes --autostart
# or copy the unit yourself:
mkdir -p "$HOME/.config/systemd/user"
cp grok-bot-tui/share/grok-tui-shell.service "$HOME/.config/systemd/user/"
loginctl enable-linger "$USER"    # sudo loginctl enable-linger "$USER" on Pi
systemctl --user daemon-reload
systemctl --user enable --now grok-tui-shell.service
tmux attach -t grok-tui
```

Detach: `Ctrl-B` then `D`. Status: `systemctl --user status grok-tui-shell`.
Disable: `systemctl --user disable --now grok-tui-shell.service`.

HDMI console (optional, not the systemd unit): autologin on tty1 and add
`grok-tui-shell` to `~/.profile` when `$(tty)` is `/dev/tty1`.

## Run

```bash
grok-tui-shell
# same: grok-bot-tui
# same: python3 -m grok_bot_tui
```

Quit: `/quit`, `/exit`, `/q`, `Ctrl-C`, `Ctrl-D`, or `Ctrl-Q`.

If grok-bot is already signed in with Gmail, the TUI opens on the **Bots**
list. If not, you get the signed-out pane.

No TTY (cron, raw systemd without tmux): the process exits 2 and tells you
to use `version` / `whoami` / `bots` / `status`.

## Non-interactive CLI

Works over SSH and on headless Pi. Never prints tokens.

```bash
grok-tui-shell version
grok-tui-shell status
grok-tui-shell whoami
grok-tui-shell bots
grok-tui-shell --json status
```

| Command | Meaning | Exit |
| --- | --- | --- |
| `tui` | Interactive (default). Needs a TTY. | 0, or 2 if no TTY |
| `version` | Title + version | 0 |
| `whoami` | GUI session label | 0 signed in, 1 signed out |
| `bots` | Roster names (same cache as the TUI) | 0 if any, 1 if none |
| `status` | arch, python, desktop yes/no, signed_in, bot count | 0 |

`man grok-tui-shell` after install (user manpath: `$HOME/.local/share/man`).

## Screen layout

Fullscreen, five rows of chrome:

```text
Grok GUI TUI shell  0.4.0                          ← header (reverse)
Bots  (N from signed-in Grok Bot)                  ← body
> ████  Night Watch             2 unread · …
  ██░░  Ops                     queue
↑↓ / j k  select   Enter  use bot   /gui  desktop
──────────────────────────────────────────────────
compose>                                           ← command / message
bot:Night Watch | signed in | shell                ← footer
```

| Region | Content |
| --- | --- |
| Header | Always `Grok GUI TUI shell` and the package version. |
| Body | Signed-out help, bot list, or one chat transcript. Notices from `/login` and `/gui` appear above the body. |
| Compose | Slash commands or a message. Prompt: `compose>`. |
| Footer | `bot:<name> \| signed in \| shell` (or `signed out` / `waiting`). |

## Sign-in (same as Grok Bot)

Grok Bot signs in at **Cursor onboarding**, not at an xAI device URL:

- Product: https://x.ai/bot
- SSO: https://cursor.com/bot/onboarding (Gmail and other IdPs the GUI allows)

### Unsigned pane

Shows **Sign in with browser** as an OSC 8 hyperlink plus the raw URL, then
https://x.ai/bot. Enter or `/login` starts SSO.

Override the printed URL with `GROK_TUI_SIGNIN_URL` (tests / staging only).

### `/login` sequence

1. Clear this TUI’s local “ignore GUI session” flag.
2. If grok-bot already looks signed in, reuse that session and load the roster.
3. Otherwise print the OSC 8 link, try `webbrowser.open` on the onboarding URL,
   and spawn `grok-bot` (never as a substitute for the GUI).
4. Poll up to **20 seconds** for GUI user-data markers.
5. Footer becomes `signed in` and the body switches to **Bots**.

Complete Gmail in the **Grok Bot window**. Retry `/login` if the poll times
out before you finish MFA.

### How “signed in” is detected

The TUI never parses Cookies. It treats the GUI as signed in when any of these
hold (under `$XDG_CONFIG_HOME/Grok Bot` and `$HOME/.grokbot`, overridable):

- `$HOME/.grokbot/settings.json` has a non-empty
  `hasSeenOnboardingAccountScope` (hashed account marker, not a token).
- `accountScopes` in that file is a non-empty object.
- Electron `Local Storage/leveldb` is larger than 2048 bytes, or
  `Session Storage` larger than 1024 bytes.

`/whoami` prints `Grok Bot GUI session`. It never prints an email or token.

### `/logout`

Signs **this TUI** out only: writes `$HOME/.grok-bot-tui/ignore-gui-session`
and clears any stored API key. Grok Bot desktop keeps its session until you
sign out there. `/login` removes the ignore file.

## Bot list

Source of truth: grok-bot’s local roster slice

`$HOME/.config/Grok Bot/sand-client-persistence/*.blob`

decoded key `…roster.last-roster` for the active account slot. Also:

| Slice | Use |
| --- | --- |
| `client-meta.account-slot` | Which Cursor/Grok Bot account the GUI last used. |
| `selection.last-agent` | Cursor on the last bot you used in the GUI. |
| `ui-agent-refs` | Pinned ids move to the top of the list. |
| `isHiddenFromSidebar` | Hidden bots are omitted, same as the GUI. |

Each row: selection mark, 4-cell sprite, name (22 cols), blurb. Blurb is the
first line of the bot description, prefixed with `N unread ·` when unread.
Group threads without a description show `group`.

`/agents` re-reads the cache (does **not** call `api.x.ai` `/models` when a
GUI session exists). If the cache is empty:

```text
No bots in the Grok Bot cache yet. Open grok-bot, then /agents.
```

Sprites: SHA-256 of the bot id → 4 bits of `█` / `░`, terminal truecolor when
`COLORTERM` is `truecolor`/`24bit` or `TERM` ends in `-direct`. Width &lt; 48
columns → `[F]` (first letter). No Kitty/Sixel.

## Keys and commands

On the bot list, with `compose>` **empty**:

| Key | Action |
| --- | --- |
| `j` / `↓` / `n` | Next bot |
| `k` / `↑` / `p` | Previous bot |
| `Enter` | Select the highlighted bot |
| `Ctrl-C` `Ctrl-D` `Ctrl-Q` | Quit |

Typed lines:

| Input | Action |
| --- | --- |
| `/login` | Grok Bot GUI SSO (launch grok-bot + Cursor onboarding). |
| `/login-key` [`<key>`] | Optional `api.x.ai` key paste. Not Grok Bot SSO. |
| `/logout` | Sign this TUI out. Desktop session is unchanged. |
| `/whoami` | `signed in  Grok Bot GUI session` or truncated key label. |
| `/agents` | Reload bots from the Grok Bot roster cache. |
| `/gui` | Launch packaged grok-bot (x86_64). |
| `/chat` [`<text>`] | Open the chat view (or send if text is given). |
| `/model` [`<id>`] | Show or set the optional api.x.ai model id. |
| `/clear` | Clear the in-memory transcript. |
| `/help` | In-TUI help (same commands). |
| `/quit` `/exit` `/q` | Exit. |
| other `/…` | `Unknown command`. |
| non-slash text on the list | Treated as **select**, not chat. |
| non-slash text in chat view | Send (see next section). |
| empty line while signed out | Same as `/login`. |

`--help` on the process (before the TUI) lists flags only.

## Talking to a bot

Selecting a bot sets the footer to `bot:<name>` and switches to the chat view.
Messages to Grok Bot **run in the desktop app**. With no API key, a send:

1. Records `you: …` in the local transcript.
2. Launches grok-bot.
3. Prints that messages run in Grok Bot, plus https://x.ai/bot.

The TUI does not inject the text into the Electron window and does not scrape
a reply. Finish the task in Grok Bot.

## Optional api.x.ai chat

`/login-key` (or `XAI_API_KEY` / `GROK_API_KEY` / `--api-key`) is a **fallback
for the xAI Responses API**, not Grok Bot SSO. When a key is present **and**
there is no GUI roster, `/agents` may show `GET /v1/models`. When a GUI
session exists, the roster always wins.

Key store (never logged in full):

1. Environment (`XAI_API_KEY`, then `GROK_API_KEY`).
2. Optional `keyring` service `grok-tui-shell`.
3. File `$HOME/.config/grok-tui-shell/credentials` mode `0600`.

`/whoami` shows a truncated label (`abcd…wxyz`). `/logout` deletes the file
and keyring entry.

Default model: `grok-4.6`. Base URL: `https://api.x.ai/v1`. Token usage from
successful API replies is appended to `$HOME/.grok-bot-tui/usage.jsonl`
(counts and model only; no key).

## Launching the desktop app

`/gui` and `/login` look for, in order:

- `grok-bot` on `PATH`
- `$HOME/.local/bin/grok-bot`, `/usr/local/bin/grok-bot`, `/usr/bin/grok-bot`
- `launch.sh` walking up from the current directory
- `$GROK_BOT_HOME/grok-bot`
- `$HOME/.local/opt/grok-bot/grok-bot`, `/opt/grok-bot/grok-bot`
  (and the older `Grok_Bot` directory names)

Prefers a wrapper (`launch.sh`) over a raw Electron binary when both exist.
Spawn uses `start_new_session=True` (detached). On aarch64 the TUI prints that
the desktop is x86_64-only.

## Config file

`$HOME/.config/grok-bot-tui/config.json` (no secrets):

```json
{
  "model": "grok-4.6",
  "base_url": "https://api.x.ai/v1",
  "timeout": 3600,
  "system": "You are a short, helpful chat in Grok GUI TUI shell. This is not Grok."
}
```

Priority: CLI flag > environment > this file > built-in default. API keys stay
in `credentials` / `XAI_API_KEY`, never in `config.json`.

## CLI flags

```text
grok-tui-shell --help
```

| Flag | Env | Default |
| --- | --- | --- |
| `--api-key` | `XAI_API_KEY` or `GROK_API_KEY` | unset |
| `--model` | `GROK_MODEL` | `grok-4.6` |
| `--system` | `GROK_SYSTEM` | short TUI system prompt (“This is not Grok.”) |
| `--timeout` | `GROK_TIMEOUT` | `3600` seconds |
| `--base-url` | `GROK_BASE_URL` | `https://api.x.ai/v1` |

These flags affect optional api.x.ai `/chat` only.

## Environment

| Variable | Purpose |
| --- | --- |
| `GROK_TUI_SIGNIN_URL` | Override onboarding URL printed by `/login`. |
| `GROK_TUI_CONFIG` | Path to `config.json` (default `$HOME/.config/grok-bot-tui/config.json`). |
| `GROK_TUI_CONFIG_DIR` | Directory for that config file. |
| `GROK_TUI_ALLOW_NOTTY` | Set to `1` to allow the TUI without a TTY (not recommended). |
| `GROK_TUI_CREDENTIALS` | Path to the API-key JSON file. |
| `GROK_BOT_TUI_HOME` | TUI data dir (ignore-flag, usage.jsonl). Default `$HOME/.grok-bot-tui`. |
| `XDG_DATA_HOME` | If `GROK_BOT_TUI_HOME` is unset: `$XDG_DATA_HOME/grok-bot-tui`. |
| `XDG_CONFIG_HOME` | Electron profile parent (`…/Grok Bot`) and TUI credentials parent. |
| `GROK_BOT_DATA` | GUI settings dir. Default `$HOME/.grokbot`. |
| `GROK_BOT_HOME` | Directory containing the `grok-bot` binary. |
| `GROK_BOT_TUI_ARCH` | Override `platform.machine()` for desktop-arch checks. |
| `COLORTERM` / `TERM` | Truecolor sprites. |

## Files and paths

Examples use `$HOME` and `/opt/grok-bot` only.

| Path | Who writes it | What |
| --- | --- | --- |
| `$HOME/.config/Grok Bot/` | grok-bot | Electron user-data. Roster cache in `sand-client-persistence/`. **Do not copy Cookies.** |
| `$HOME/.grokbot/settings.json` | grok-bot | Onboarding / account-scope markers. |
| `$HOME/.grok-bot-tui/ignore-gui-session` | this TUI | `/logout` opt-out. |
| `$HOME/.grok-bot-tui/usage.jsonl` | this TUI | Optional API token counts. |
| `$HOME/.config/grok-bot-tui/config.json` | this TUI | Non-secret defaults (model, timeout, base_url). Created by `install.sh`. |
| `$HOME/.config/grok-tui-shell/credentials` | this TUI | Optional API key, mode `0600`. |
| `$HOME/.config/systemd/user/grok-tui-shell.service` | `install.sh --autostart` | User unit; tmux session `grok-tui`. |
| `/opt/grok-bot/grok-bot` | installer | System desktop binary. |

## Privacy

- No Cookies, no `sand-secrets.json`, no token scrape.
- `/whoami` never prints a full key or email.
- Roster rows keep `id`, `name`, and a short blurb only (no `lastEntry` text).
- Docs and tests use `$HOME`, `/opt/grok-bot`, and `user@example.org`.

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Header `0.3.0` and bots named Sales Outbound / Talent Scout / Chief of Staff | Stale install. `./grok-bot-tui/install.sh --yes`, quit the TUI, run `grok-tui-shell` again. Header must be **0.4.0** and the list heading must say `from signed-in Grok Bot`. |
| Signed out even though grok-bot shows Gmail | `/login`, or check `$HOME/.grokbot/settings.json` exists for this user. `XDG_CONFIG_HOME` must match the desktop. |
| `No bots in the Grok Bot cache yet` | Open grok-bot so it writes `sand-client-persistence`, then `/agents`. |
| List does not match the GUI | `/agents`. Hidden bots stay hidden. Pin order follows the GUI. |
| `/login` says grok-bot not found | Install the desktop on x86_64; put `grok-bot` on `PATH` or under `/opt/grok-bot`. |
| `/gui` on a Pi / arm64 | Expected: desktop is x86_64-only. TUI still runs. |
| OSC 8 does not click | Copy the raw `https://cursor.com/bot/onboarding` line. |
| `/logout` still shows bots after restart | `/logout` only ignores the GUI session for this TUI. Sign out inside grok-bot to end the desktop session, or leave the ignore file in place. |
| Wrong Python / two copies | `type grok-tui-shell`; `python3 -m pip show grok-bot-tui`. Editable location must be this clone. |

## Tests and development

```bash
python3 -m pip install --user -e "./grok-bot-tui[dev]"
PYTHONPATH=grok-bot-tui/src python3 -m pytest grok-bot-tui/tests
```

Tests are offline: no live SSO, no Cookie fixtures, no network to Cursor.
They write fake roster blobs under a temp `XDG_CONFIG_HOME`.

Module map (under `src/grok_bot_tui/`):

| File | Role |
| --- | --- |
| `app.py` | Fullscreen UI, commands, fill-from-roster. |
| `grok_bot_session.py` | GUI session heuristic + roster reader. |
| `gui.py` | Find and spawn grok-bot. |
| `auth.py` | OSC 8 links, optional API-key store. |
| `pixel.py` | Hash sprites. |
| `client.py` / `agents.py` | Optional api.x.ai only. |
