# grok-bot-tui

**Grok Bot companion** — a keyboard TUI around Grok Bot, not Grok the chat app.

Status line: **grok-bot-tui · Grok Bot companion**.

## The split (do not blur)

| Product | What it is | This TUI |
| --- | --- | --- |
| **Grok** | Chat at [https://grok.com](https://grok.com) and the xAI Responses API | Wrong target. Optional `/chat` only, labeled **Grok API (not Grok Bot)**. |
| **Grok Bot** | Teammate product ([https://x.ai/bot](https://x.ai/bot), [launch post](https://x.ai/news/introducing-grok-bot)): persistent bots, own computer, approvals, routines | **This companion.** |

On Linux this repo already packages (1) the community Grok Bot desktop as `grok-bot` and (2) the official CLI `grok` (help text starts **Grok Build TUI**; often `~/.grok/bin/grok`). This process does not invent a second chat product and does not replace either binary.

## What this is

1. `/gui` opens **Grok Bot**: packaged `grok-bot` desktop if it is on PATH or this repo's install prefix (`/opt/grok-bot`, `~/.local/opt/grok-bot`, …), else [https://x.ai/bot](https://x.ai/bot). Never grok.com.
2. Default action is the official `grok` CLI. Empty Enter or `/grok [args]` execs that binary. Flags are pass-through from `grok --help` only (do not invent extras). `/plan` launches official plan mode (the CLI's `--no-plan` *disables* plan).
3. `/sessions` is a read-only listing of official `~/.grok` metadata. Credentials (`auth.json`, etc.) are skipped. This TUI never writes auth or pretends local files are Grok Bot state.
4. Optional `/chat` is **Grok API (not Grok Bot)** when `XAI_API_KEY` or `GROK_API_KEY` is set.

## What this is not

- Not Grok the chat app, not a rebrand of grok.com, not a standalone chat replacement.
- Not a reconstruction of Grok Bot 0.18, not a clone of OpenMausBot, not a scrape of the desktop UI.
- Official prompts from [xai-org/grok-prompts](https://github.com/xai-org/grok-prompts) are **not vendored** (AGPL-3.0) and are not this app's identity. `/prompt <id>` (optional API extra) fetches them at runtime into `~/.grok-bot-tui/prompts/` with the AGPL notice.
- `/analyze` does not scrape X. No Playwright, no harvested cookies, no auth bypass.
- Out of scope: computer-use, connectors, cron, MCP host.

Optional `/chat` **bills the operator's xAI account**. Never commit a key. `Authorization` is never logged.

## Install

Python 3.11+. From the repository root:

```bash
pip install -e ./grok-bot-tui
```

```bash
pip install -e "./grok-bot-tui[dev]"
pytest grok-bot-tui/tests
```

Install the official CLI (Grok Build TUI) with `./scripts/install-cli.sh` or [https://x.ai/cli/install.sh](https://x.ai/cli/install.sh). Expected on PATH or `~/.grok/bin/grok`.

## Run

No API key required (desktop / `x.ai/bot` + official `grok`):

```bash
python -m grok_bot_tui
# or:
grok-bot-tui
```

Optional Grok API (not Grok Bot):

```bash
export XAI_API_KEY="your_api_key"
python -m grok_bot_tui
```

```bash
grok-bot-tui --help
```

`--help` and `/help` print **Grok Bot companion**. Commands include `/gui /grok /plan`. grok.com is not the happy path.

## Commands

| Input | Action |
| --- | --- |
| Enter | Launch official `grok` (Grok Build TUI) with no extra flags |
| `/grok [flags]` | Same binary; flags must appear in `grok --help` |
| `/plan [flags]` | Official grok plan mode (do not pass `--no-plan`) |
| `/gui` | Launch packaged `grok-bot`, else [https://x.ai/bot](https://x.ai/bot) |
| `/help` | List commands |
| `/clear` | Clear local scratch notes (not Grok Bot state) |
| `/notes` | Local scratch pane |
| `/sessions` | Read-only summary of official `~/.grok` (skips credentials) |
| `/chat` | Optional **Grok API (not Grok Bot)**; needs a key |
| `/chat …` | Send one API line immediately if a key is set |
| `/prompt` | List official prompt ids (xai-org/grok-prompts), API extra only |
| `/prompt <id>` | Fetch/cache that published prompt for later `/chat` |
| `/prompt off` | Drop extra prompt |
| `/analyze <url>` | Explain-this-link via Grok API, or a local note if no key |
| `/model [name]` | Show or switch Grok API model (default `grok-4.6`) |
| `/quit` | Exit (`/exit`, Ctrl+C, Ctrl+D) |

If a `/chat` or `/analyze` response includes usage, the footer shows last-turn + totals and one JSONL line is appended to `~/.grok-bot-tui/usage.jsonl`. That cache is local scratch, not Grok Bot sessions.

Flags: `--model`, `--system`, `--timeout`, `--api-key` (prefer env). Those apply to optional `/chat` only.

Official `grok` flags (from `grok --help`; do not invent extras): `--agent`, `--allow` / `--deny`, `--always-approve`, `--continue`, `--no-plan`, `--no-subagents`, `--model`.

## Sample session

```text
Grok Bot companion  grok-bot-tui 0.1.4
Grok Bot companion. /gui → grok-bot or https://x.ai/bot. Default: official grok CLI.
grok> /gui
Launched Grok Bot desktop: /opt/grok-bot/grok-bot
grok> /grok --help
Running /home/you/.grok/bin/grok --help
grok> /quit
```

Footer/status: `grok-bot-tui  ·  Grok Bot companion  ·  official grok CLI  ·  /help /gui /grok /quit`
