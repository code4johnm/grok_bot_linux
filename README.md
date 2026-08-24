# grok_bot_linux

GitHub description: "Grok bot linux for Kali Linux".

This repository is a stub. The default branch (`main`) started as a
single-file tree: this `README.md` and no application code. There is no
bot, installer, systemd unit, API client, or Kali package here.

## Contents

| Path | Role |
| --- | --- |
| `README.md` | This file |
| `.markdownlint.yaml` | Markdown lint rules used by CI |
| `.github/workflows/ci.yml` | Markdown lint on `main` and pull requests |

## CI

GitHub Actions is the only automation. The workflow runs
[markdownlint-cli2](https://github.com/DavidAnson/markdownlint-cli2)
against `*.md` files. There is no application test suite because there
is no application code.

## Status

Do not treat this as a working Kali Linux bot. Add application files
before documenting install or run steps.
