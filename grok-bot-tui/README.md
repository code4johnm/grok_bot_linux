# Grok GUI TUI shell

Companion terminal client for the Grok GUI. **This is not Grok** and is not a
rebrand of Grok Bot. Footer/title: `Grok GUI TUI shell`.

## Sign-in (honest MVP)

True “click link → authorize app → TUI signed in” needs an **official**
OAuth or device-code flow. xAI’s public API today is **API keys** from the
console ([docs.x.ai quickstart](https://docs.x.ai/developers/quickstart)).
This shell does **not** scrape cookies or pretend to be an OAuth client.

Easy sign-on:

1. Unsigned view: OSC 8 **Sign in with browser** plus the raw URL
   (`https://console.x.ai/team/default/api-keys`). Terminals without OSC 8
   still get the URL.
2. Enter or `/login` opens that page (`webbrowser.open`).
3. Paste the key **once** at `compose>` (or `/login <key>`).
4. `XAI_API_KEY` / `GROK_API_KEY` still work non-interactively.

Credentials: keyring when available, else
`$HOME/.config/grok-tui-shell/credentials` mode `0600`. Never printed in full.
`/whoami` shows a truncated label. `/logout` clears the store.

`auth.build_authorize_url` exists only as a hook if xAI later publishes a
public OAuth client. It is not the default path.

Pixel “bots” in the terminal are hash-based half-block sprites and work
whether you signed in via paste or env.

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
Open the official console, create a key, paste it once.
compose> xai-…                ← paste once (never logged in full)
signed in as xai-…abcd
Agents / models
> ██▀▄…  grok-4.6
    flagship  grok-4.6
agent:grok-4.6 | signed in | shell
compose>
```
