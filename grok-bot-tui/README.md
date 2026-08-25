# Grok GUI TUI shell

Companion terminal client for the Grok GUI. **This is not Grok** and is not a
rebrand of Grok Bot. Footer/title: `Grok GUI TUI shell`.

## Sign-in (same as Grok Bot)

Grok Bot and the official `grok` CLI sign in with **OIDC at
`https://accounts.x.ai`** (SSO such as Gmail). That is the TUI path too.

1. Unsigned view: OSC 8 **Sign in with browser** plus the raw URL
   `https://accounts.x.ai/sign-in`.
2. `/login` or Enter runs official `grok login --device-auth`.
3. The TUI prints a clickable
   `https://accounts.x.ai/oauth2/device?user_code=…` link and the code.
4. Finish SSO in the browser. The CLI writes `$HOME/.grok/auth.json`.
5. `/whoami` shows a truncated name/email, never the token.
6. `/logout` runs `grok logout`.

If you are already signed into `grok` / Grok Bot, the TUI reuses that session.
It does **not** read Electron cookies under `$HOME/.config/Grok Bot`.

`/login-key` is an optional **API-key** fallback for `api.x.ai` chat only
(`XAI_API_KEY`). That is not Grok Bot SSO.

## Agents / models

After SSO, the pane **Agents / models** lists models from the grok CLI cache
(`$HOME/.grok/models_cache.json`) or `GET /v1/models` if an API key is set.
Each row has a pixelated half-block sprite (`▀▄█`) from a hash of the id.

- `j` / `k` move; Enter binds chat.
- `/agents` refreshes. Narrow terminals collapse to `[A]`.
- No Kitty/Sixel in v1.

Status: `agent:<name> | signed in | shell`.

## Install

```bash
pip install -e "./grok-bot-tui[dev]"
pytest grok-bot-tui/tests
grok-tui-shell
```

Requires the official grok CLI on PATH for SSO (`curl -fsSL https://x.ai/cli/install.sh | bash`).

## Commands

| Input | Action |
| --- | --- |
| `/login` | Grok Bot SSO (device URL + browser) |
| `/login-key` | Optional API-key paste |
| `/logout` `/whoami` | Sign out / truncated label |
| `/agents` | Refresh list |
| `j` `k` Enter | Navigate / select |
| `/gui` | Packaged grok-bot desktop (x86_64) |
| `/help` `/quit` | Help / exit |

## Demo

```text
Grok GUI TUI shell
signed out
Sign in with browser
https://accounts.x.ai/sign-in
compose> /login
Complete sign-in in browser… (same SSO as Grok Bot: Gmail, etc.)
https://accounts.x.ai/oauth2/device?user_code=ABCD-1234
Confirm this code in the browser: ABCD-1234
signed in as Operator (u***@example.org)
Agents / models
> ██▀▄  Grok 4.6
    SpaceXAI's latest frontier model  grok-4.6
agent:Grok 4.6 | signed in | shell
```
