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
- `/analyze` does not scrape X and does not use the X API; it only sends the URL text to the optional API companion.
- Official prompts from [xai-org/grok-prompts](https://github.com/xai-org/grok-prompts) are **not vendored** (AGPL-3.0). `/prompt <id>` fetches them at runtime into `~/.grok-bot-tui/prompts/` (or `$GROK_BOT_TUI_HOME` / XDG) and keeps the AGPL notice plus source URL in that cache.

Optional API usage **bills the operator's xAI account**. Never commit a key. `Authorization` is never logged. Session directories never store keys.

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

`--help` prints **Grok GUI TUI shell** and lists `/gui /prompt /analyze /plan /sessions /model`.

## Commands

| Input | Action |
| --- | --- |
| `/gui` | Open/focus official Grok GUI (`https://grok.com`) |
| `/help` | List commands |
| `/clear` | Clear the local pane (does not delete saved sessions) |
| `/notes` | Local note buffer |
| `/chat` | Switch to API companion (not GUI); needs a key |
| `/chat …` | Send one API line immediately if a key is set |
| `/plan …` | Hold the next API turn (no network until approved) |
| `y` `/send` `/approve` | Send the pending plan |
| `n` `/cancel` `/reject` | Drop the pending plan |
| `/prompt` | List official prompt ids (xai-org/grok-prompts) |
| `/prompt <id>` | Fetch/cache that published prompt for later `/chat` |
| `/prompt off` | Drop extra prompt |
| `/analyze <url>` | Explain-this-link via API companion, or a local note if no key |
| `/model [name]` | Show or switch model (default `grok-4.6`) |
| `/sessions` `/new` `/open` `/forget` | Durable session dirs under `~/.grok-bot-tui/sessions/<name>/` |
| `/quit` | Exit (`/exit`, Ctrl+C, Ctrl+D) |

Sessions are directories (`state.json`, `notes.txt`, `transcript.json`) and reload on the next start. If a `/chat` or `/analyze` response includes usage, the footer shows last-turn + session totals and one JSONL line is appended to `~/.grok-bot-tui/usage.jsonl`. Plan `y`/`n` appends `plan-approved` or `plan-cancelled` only. If a number is missing, it is omitted.

Flags: `--model`, `--system`, `--timeout`, `--gui-url`, `--api-key` (prefer env). Defaults match current xAI docs (`grok-4.6`, `https://api.x.ai/v1`).

## Sample session

```text
Grok GUI TUI shell  grok-bot-tui 0.1.3
Grok GUI companion. Official GUI: https://grok.com
note> /gui
Opened official Grok GUI: https://grok.com
api> /plan summarize this note for grok.com
Plan held. y / /send to call the API companion, n / /cancel to drop.
api> n
Plan cancelled.
note> /quit
```

Footer/status: `grok-bot-tui  ·  Grok GUI companion  ·  local notes  ·  /help /gui /clear /quit`
