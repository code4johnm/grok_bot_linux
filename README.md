# grok-bot

Small Python 3.11+ CLI and local daemon for Linux. It keeps a workspace
directory under `~/.local/share/grok-bot` and sends a prompt to the official
xAI Grok HTTP API (`https://api.x.ai/v1/chat/completions`) using
`GROK_API_KEY` or `XAI_API_KEY` from the environment. The reply is printed on
stdout.

This repository is not an official xAI or Grok desktop application, not a Kali
package, and not a GUI. It does not bundle API keys.

## Requirements

- Linux
- Python 3.11 or newer
- An xAI API key from [console.x.ai](https://console.x.ai)

## Clone and build

```bash
git clone https://github.com/code4johnm/grok_bot_linux.git
cd grok_bot_linux
make
make test
make install
```

`make` byte-compiles the package. `make test` runs the offline pytest suite
(HTTP is mocked). `make install` copies the program to `~/.local` (`PREFIX`
overrides the destination).

From a checkout you can also run `./bin/grok-bot` without installing.

## Installer

```bash
./install.sh                  # ~/.local/bin/grok-bot
./install.sh --system         # /usr/local
./install.sh --prefix DIR
./install.sh --systemd        # also enable a systemd --user unit
./install.sh --uninstall      # remove bin/lib/unit; keep the workspace
```

If `~/.local/bin` is not on `PATH`, add it in your shell rc:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## API key

Create a key in the xAI console. Export it in the shell that runs `grok-bot`.
Never commit the value.

```bash
export XAI_API_KEY="your-key"
# or
export GROK_API_KEY="your-key"
```

Optional settings:

| Variable | Meaning | Default |
| --- | --- | --- |
| `GROK_MODEL` | Model id | `grok-4` |
| `GROK_API_BASE` | API origin | `https://api.x.ai/v1` |
| `GROK_TIMEOUT` | HTTP timeout seconds | `120` |
| `GROK_BOT_WORKSPACE` | Workspace directory | `~/.local/share/grok-bot` |

For the user service, put the key in a file that is not in git:

```bash
mkdir -p ~/.config/grok-bot
printf 'XAI_API_KEY=%s\n' "your-key" > ~/.config/grok-bot/env
chmod 600 ~/.config/grok-bot/env
systemctl --user restart grok-bot
```

## Run

```bash
grok-bot ask "What is 2+2?"
echo "Summarize this" | grok-bot ask
grok-bot status
grok-bot version
```

`grok-bot ask` calls the API from the CLI process. If the daemon is already
running, the CLI forwards the prompt over the workspace Unix socket instead.
Use `--direct` to skip the daemon.

Foreground daemon (same process systemd starts):

```bash
grok-bot daemon
```

Optional user service after `./install.sh --systemd`:

```bash
systemctl --user enable --now grok-bot
systemctl --user status grok-bot
```

The workspace stores `history.jsonl`, `daemon.pid`, and `grok-bot.sock`. It
never stores the API key.

## Layout

```text
src/grok_bot/     CLI, HTTP client, daemon, workspace
tests/            Offline pytest (mocked HTTP)
bin/grok-bot      Run from a source checkout
install.sh        ~/.local or /usr/local, optional systemd --user
Makefile          make / make test / make install
systemd/          Example grok-bot.service
requirements.txt  pytest pin for make test
```

## License

MIT. See `LICENSE`. The xAI API and Grok models are separate products with
their own terms.
