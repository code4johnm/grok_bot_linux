# grok-bot-tui

Terminal thread for the **grok-bot** Electron app. This is not Grok.

One screen: header (current bot + `grok-bot-tui`), transcript (`you:` / `bot:`), compose line. Footer: `grok-bot-tui`.

## What this is

- Typing or `/chat` sends xAI Responses when `XAI_API_KEY` or `GROK_API_KEY` is set. Chat is a TUI feature, not a rebrand of Grok.
- `/gui` launches packaged `grok-bot` on x86_64 (`PATH`, `/opt/grok-bot/grok-bot`, `~/.local/opt/grok-bot/grok-bot`, or this repo’s `launch.sh`).
- `/bot <name>` renames the current thread. `/model` `/clear` `/help` `/quit`.

Does not replace, rename, or remove the Electron grok-bot tree. Does not exec the official `grok` CLI. No computer preview, plugins, routines, MCP, or browser automation.

## Install

Python 3.11+, httpx, prompt_toolkit. 256-color or monochrome. No Textual, Electron, or extra daemons.

```bash
./scripts/install-tui.sh
# or:
./scripts/install-for.sh --tui-only
# or:
pip install -e ./grok-bot-tui
```

```bash
pip install -e "./grok-bot-tui[dev]"
pytest grok-bot-tui/tests
```

```bash
export XAI_API_KEY="your_api_key"   # optional, for /chat
grok-bot-tui
```

## Raspberry Pi / aarch64

This repo’s packaging README: Electron grok-bot desktop is **x86_64 only**. There is no working desktop tarball for arm64. The official `grok` CLI supports aarch64; this TUI does **not** use that CLI as the product.

`grok-bot-tui` is intended to run on aarch64 (Pi 4/5 and other SBCs) and on x86_64. Use the TUI-only installer above — it does not install Electron grok-bot.

On aarch64 (or when `grok-bot` is missing), `/gui` prints that the desktop is x86_64-only and chat still works.

This change was not run on a physical Raspberry Pi.

## Commands

| Input | Action |
| --- | --- |
| text | Send chat (needs a key) |
| `/chat …` | Same send |
| `/gui` | Launch grok-bot on x86_64; otherwise x86_64-only / missing message |
| `/bot <name>` | Rename this thread (default `grok-bot`) |
| `/model [name]` | Show or switch /chat model |
| `/clear` | Clear transcript |
| `/help` `/quit` | Help / exit |

## Sample

```text
grok-bot  ·  grok-bot-tui
grok-bot-tui 0.1.6. This is not Grok.
(no messages)
compose> /gui
Launched grok-bot: /usr/local/bin/grok-bot
compose> /quit
```

Footer: `grok-bot-tui`
