# grok-tui

Minimal keyboard-only TUI chat with Grok. One process, one screen, in-memory
session history. No accounts, plugins, web UI, tools, MCP, voice, images, or
telemetry.

This package lives next to the existing **Grok Bot Linux** desktop/CLI
packaging. It does **not** replace `grok-bot` or the official `grok` CLI.

## API (current xAI docs, 2026)

Verified from [Quickstart](https://docs.x.ai/developers/quickstart) and
[Generate text](https://docs.x.ai/developers/model-capabilities/text/generate-text):

| Item | Value |
| --- | --- |
| Base URL | `https://api.x.ai/v1` |
| Endpoint | `POST /v1/responses` (Responses API) |
| Model | `grok-4.6` |
| Auth | `Authorization: Bearer` from `XAI_API_KEY` or `GROK_API_KEY` |

[Chat Completions](https://docs.x.ai/developers/rest-api-reference/inference/legacy)
(`/v1/chat/completions` and other compat endpoints) is documented as
legacy/deprecated. This client does not call it.

Streaming uses `"stream": true` on the Responses create body (see
[Streaming](https://docs.x.ai/developers/model-capabilities/text/streaming) and
the `stream` transport field on
[Create new response](https://docs.x.ai/developers/rest-api-reference/inference/chat#create-new-response)).
Tokens are printed as SSE deltas arrive.

**Usage bills the operator's xAI account.** You pay for tokens this process
sends. Never commit a key. The client never logs `Authorization`.

## Install

Python 3.11+. From the repository root:

```bash
pip install -e ./grok-tui
```

Dev / tests:

```bash
pip install -e "./grok-tui[dev]"
pytest grok-tui/tests
```

## Run

```bash
export XAI_API_KEY="your_api_key"
python -m grok_tui
# or:
grok-tui
```

`GROK_API_KEY` is accepted if `XAI_API_KEY` is unset.

## Flags and environment

| Flag | Environment | Default |
| --- | --- | --- |
| `--api-key` | `XAI_API_KEY` / `GROK_API_KEY` | (required) |
| `--model` | `GROK_MODEL` | `grok-4.6` |
| `--system` | `GROK_SYSTEM` | short helpful terminal assistant |
| `--timeout` | `GROK_TIMEOUT` | `3600` seconds (reasoning-friendly, per docs) |
| `--base-url` | `GROK_BASE_URL` | `https://api.x.ai/v1` |

```bash
XAI_API_KEY=... python -m grok_tui --model grok-4.6 --system "Be terse." --timeout 120
```

A missing key prints a clear message and exits non-zero.

## Commands

| Input | Action |
| --- | --- |
| `/help` | List commands |
| `/clear` | Drop in-memory history (keeps the system prompt) |
| `/model` | Show the current model |
| `/model <id>` | Switch model for later turns |
| `/quit` | Exit (`/exit`, Ctrl+C, Ctrl+D also quit) |

Network and rate-limit failures print one line and leave the loop running.

## TUI stack

`prompt_toolkit` `PromptSession` plus a printed transcript. Dependency set is
`httpx` + `prompt_toolkit` only.
