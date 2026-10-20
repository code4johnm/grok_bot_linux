# Grok cloud ↔ laptop agent — async-index

Code for the cloud agent (Creator Bot) ↔ laptop agent architecture built around
the Google Drive folder **"Grok"** (`jobs4johnm@gmail.com`).

> **Where things live**
> - **Code** (this directory, `code4johnm/grok_bot_linux/async-index/`) = all
>   `.py`, systemd units, templates, docs.
> - **Drive/Grok** = lightweight files only: log/status/heartbeat JSON, index
>   messages (`msg-*.yaml`, `reply-*.yaml`), and `channel-config.yaml`.
>   **No code in Drive.**

## Files

| File | What it is |
|------|------------|
| `webhook_receiver.py` | stdlib HTTP receiver for Drive push notifications. Validates `X-Goog-Channel-Token`, returns 204, logs to `~/.grok/webhook.log`. **On-demand / short-lived, not a 24/7 daemon** (see Security). |
| `grok-webhook.service` | systemd unit for the receiver (use only if you choose to run it; prefer on-demand — see Security). |
| `async-monitor.py` | the index monitor. `--watch-folder` (fallback, zero ports) or `--changes-api` (needs laptop Google creds). Writes `reply-*.yaml`, idempotent via `~/.grok/processed-ids.txt`. |
| `heartbeat.py` | one ICMP ping (TCP fallback); writes `{method,timestamp,status}` JSON into Drive/Grok. |
| `grok-heartbeat.service` / `.timer` | run heartbeat every 5 minutes. |
| `channel-config.template.yaml` | template to fill in when the laptop registers the watch. |

## Install order (on the laptop)

1. `sudo mkdir -p /opt/grok && sudo cp *.py /opt/grok/`
2. Create the webhook token (never commit it):
   ```
   mkdir -p ~/.grok
   printf 'WEBHOOK_TOKEN=%s\n' "$(openssl rand -hex 24)" > ~/.grok/webhook.conf
   chmod 600 ~/.grok/webhook.conf
   ```
3. **Heartbeat** (safe, no open ports):
   ```
   sudo cp grok-heartbeat.service grok-heartbeat.timer /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now grok-heartbeat.timer
   ```
4. **Index monitor — fallback watch-folder mode (recommended, no ports):**
   ```
   python3 /opt/grok/async-monitor.py --watch-folder \
     --grok-dir ~/GoogleDrive/Grok --agent-name laptop
   ```
   (Point `--grok-dir` at wherever your Drive client syncs the Grok folder.)

## Security model — eliminate persistent open attack surface

- **Primary path: Drive-synced folder watcher.** `async-monitor.py --watch-folder`
  opens **zero ports**, needs no public IP, and works immediately with the
  Google Drive desktop sync client. This is the default and the safe path.
- **Secondary path: webhook receiver, on-demand / short-lived only.** The
  receiver is correct code, but should **not** run as a 24/7 public daemon on an
  open port. Run it only for the duration of a fast message exchange, e.g. open
  a public→private port forward just-in-time, do the exchange, then close it;
  or front it with a Cloudflare Tunnel that terminates TLS and can be brought
  up/down on demand. **Do not leave port 80/8080 exposed to the internet 24/7.**
- No secrets in logs. The channel token lives only in `~/.grok/webhook.conf`
  (mode 600) and `channel-config.yaml`; it is never logged or echoed in replies.

## Drive push (changes.watch) limitation — read this

Google Drive Changes API **push** requires the webhook address to be an **HTTPS
URL on a domain that is verified in the Google API Console**. Google will **not**
deliver push notifications to:

- a **bare IP address** (e.g. `http://203.0.113.5/webhook`), or
- **plain http on port 80**.

So binding `0.0.0.0:80` on a static IP is valid code but **will never receive
Drive push** until it is fronted by a verified HTTPS domain.

- **Now / fallback:** use `async-monitor.py --watch-folder` (no ports, no push).
- **Future:** put the receiver behind a **verified HTTPS domain** or a
  **Cloudflare Tunnel** (`https://grok.example.com/webhook`), verify the domain
  in the Google API Console, then register the watch.

## Register the watch channel (FROM THE LAPTOP, with its own creds)

`changes.watch`, `changes.getStartPageToken`, and `changes.list` are **not**
available through Creator Bot's connector — they need the laptop's Google
credentials. On the laptop:

1. `pip install google-api-python-client google-auth google-auth-oauthlib`
2. Get a start page token: `drive.changes.getStartPageToken()`.
3. Call `drive.changes.watch()` with:
   - `id` = a UUID (your `channel_id`)
   - `type` = `web_hook`
   - `address` = your **verified HTTPS** `/webhook` URL
   - `token` = the same secret from `~/.grok/webhook.conf`
4. Save `channel_id`, `resource_id` (`X-Goog-Resource-ID`), `token`,
   `page_token`, `expiration`, `webhook_url` into
   `channel-config.yaml` in the Drive/Grok folder (use
   `channel-config.template.yaml`).
5. Run the push consumer: `python3 async-monitor.py --changes-api --grok-dir ~/GoogleDrive/Grok`.

## Verify

1. `touch ~/GoogleDrive/Grok/test-$(date +%s).yaml` (or drop a `msg-*.yaml`).
2. **Watch-folder mode:** tail `~/.grok/async-monitor.log`; you should see a
   `PROCESS`/`REPLY` line and a new `reply-*.yaml` in Drive/Grok.
3. **Webhook mode:** tail `~/.grok/webhook.log`; a `NOTIFY` line should appear
   (only once a verified HTTPS front end is in place).
