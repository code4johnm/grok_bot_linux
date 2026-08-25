# Grok GUI TUI shell

Companion terminal client for the Grok GUI. **This is not Grok** and is not a
rebrand of Grok Bot. Footer/title: `Grok GUI TUI shell`.

## Sign-in

xAI’s public API uses **API keys** from the console (see
[docs.x.ai quickstart](https://docs.x.ai/developers/quickstart)). There is no
documented third-party OAuth client for companion apps, so this shell does
**not** scrape browser cookies.

1. Unsigned view shows an OSC 8 hyperlink **Sign in with browser** plus the
   raw URL (copy/paste if the terminal has no OSC 8).
2. Press Enter or `/login` to open `https://console.x.ai/team/default/api-keys`.
3. Create a key, paste it into the TUI (or hit
   `http://127.0.0.1:<ephemeral-port>/callback?api_key=…` on loopback).
4. `XAI_API_KEY` / `GROK_API_KEY` still work for non-interactive auth.

Credentials: platform keyring when available, else
`$HOME/.config/grok-tui-shell/credentials` mode `0600`. Never printed in full.
`/whoami` shows a truncated label. `/logout` deletes the store.

Loopback needs a free `127.0.0.1` port. If `XAI_OAUTH_CLIENT_ID` is set, the
shell can build a standard authorize URL (`auth.build_authorize_url`).

## Agents / models

After sign-in, **Agents / models** lists `GET /v1/models` (official list; custom
bots are shown as models if that is all the API returns). Each row has a
pixelated half-block sprite (`▀▄█`) from a hash of the id, plus name, blurb,
and truncated id.

- `j` / `k` move the selection; Enter binds chat to that agent.
- `/agents` refreshes. Narrow terminals collapse the sprite to `[A]`.
- Truecolor when `COLORTERM` says so; otherwise 16-color. No Kitty/Sixel in v1.

Status line: `agent:<name> | signed in | shell`.

## Install

```bash
pip install -e "./grok-bot-tui[dev]"
pytest grok-bot-tui/tests
grok-tui-shell
# or: grok-bot-tui
```

## Commands

| Input | Action |
| --- | --- |
| `/login` | Browser link + paste key |
| `/logout` `/whoami` | Sign out / truncated label |
| `/agents` | Refresh list |
| `j` `k` Enter | Navigate / select agent |
| text `/chat` | Send to active agent |
| `/gui` | Packaged grok-bot desktop (x86_64) |
| `/help` `/quit` | Help / exit |

## Demo walkthrough

```text
Grok GUI TUI shell
signed out
Sign in with browser          ← OSC 8 (also printed as raw URL)
https://console.x.ai/team/default/api-keys
Press Enter to open the browser, then paste the key, or /login
compose> /login
Complete sign-in in browser…
compose> xai-…                ← paste (never logged in full)
signed in as xai-…abcd
Agents / models
> ██▀▄…  grok-4.6
    flagship  grok-4.6
agent:grok-4.6 | signed in | shell
compose>
```
