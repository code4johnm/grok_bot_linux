# grok-bot-tui

**Grok GUI TUI shell** — a companion TUI around the official Grok GUI.

Status line: **Grok GUI companion**.

## What this is

A keyboard-only terminal shell that:

1. Opens or focuses the official Grok GUI (`/gui` → [https://grok.com](https://grok.com), the web app documented at [docs.x.ai/grok](https://docs.x.ai/grok/overview)).
2. Keeps a **local note buffer** so the TUI is useful with no API key.
3. Optionally talks to the documented xAI Responses API (`POST /v1/responses`) when `XAI_API_KEY` or `GROK_API_KEY` is set. That pane is labeled **API companion (not GUI)**.

Work primarily in official Grok. This process does not replace Grok, the Grok mobile apps, or the `grok-bot` Linux desktop package in this repo.

## What this is not

- Not Grok the product, not a rebrand of Grok, not a standalone chat replacement.
- Not a scrape of grok.com or any other site. `/gui` only opens the official URL in your default browser (`webbrowser.open`). No Playwright, no harvested cookies, no auth bypass.
- Not accounts, plugins, web UI, tools, MCP, voice, images, or telemetry.

Optional API usage **bills the operator's xAI account**. Never commit a key. `Authorization` is never logged.

## Install

Python 3.11+. From the repository root:

```bash
pip install -e ./grok-bot-tui
```

```bash
pip install -e "./grok-bot-tui[dev]"
pytest grok-bot-tui/tests
```

## Run

No key required (GUI launcher + local notes):

```bash
python -m grok_bot_tui
# or:
grok-bot-tui
```

Optional API companion:

```bash
export XAI_API_KEY="your_api_key"
python -m grok_bot_tui
```

```bash
grok-bot-tui --help
```

`--help` prints **Grok GUI TUI shell**.

## Commands

| Input | Action |
| --- | --- |
| `/gui` | Open/focus official Grok GUI (`https://grok.com`) |
| `/help` | List commands |
| `/clear` | Clear the local pane (notes + API history) |
| `/notes` | Local note buffer |
| `/chat` | Switch to API companion (not GUI); needs a key |
| `/chat …` | Send one API line if a key is set |
| `/quit` | Exit (`/exit`, Ctrl+C, Ctrl+D) |

Flags: `--model`, `--system`, `--timeout`, `--gui-url`, `--api-key` (prefer env). Defaults match current xAI docs (`grok-4.6`, `https://api.x.ai/v1`).

## Sample session

```text
Grok GUI TUI shell  grok-bot-tui 0.1.1
Grok GUI companion. Official GUI: https://grok.com
note> /gui
Opened official Grok GUI: https://grok.com
note> draft a question for the official GUI
note: draft a question for the official GUI
note> /chat
No API key. Local notes only. Set XAI_API_KEY or GROK_API_KEY for API companion (not GUI).
note> /clear
note> /quit
```

Footer/status: `grok-bot-tui  ·  Grok GUI companion  ·  local notes  ·  /help /gui /clear /quit`
