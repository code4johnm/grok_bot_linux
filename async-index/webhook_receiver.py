#!/usr/bin/env python3
"""
webhook_receiver.py — lightweight Google Drive Changes API push receiver.

PURPOSE
-------
Receives Drive "changes.watch" push notifications over HTTP, validates the
channel token, and appends a log line for each notification. It immediately
returns HTTP 204 (No Content), which is what Google's push service expects.

IMPORTANT REAL-WORLD LIMITATION (read before deploying)
-------------------------------------------------------
Google Drive Changes API push notifications (changes.watch) require the webhook
"address" to be an HTTPS URL on a domain that is VERIFIED in the Google API
Console (Domain verification). Google will NOT deliver push notifications to:
  * a bare IP address (e.g. http://203.0.113.5/webhook), or
  * plain http on port 80.
So binding 0.0.0.0:80 on a static IP is correct code, but Google's push service
will refuse to register/deliver to it until it's fronted by a verified HTTPS
domain (e.g. a reverse proxy / TLS termination on https://grok.example.com/webhook
whose domain is verified in the API Console).

If you do not have a verified HTTPS domain, DO NOT rely on push. Use the
fallback in async-monitor.py (--watch-folder mode), which watches the locally
Drive-synced "Grok" folder and needs no open port and no Changes API.

CONFIG
------
The channel token is read from a config file (never hardcoded):
    ~/.grok/webhook.conf
containing a line:
    WEBHOOK_TOKEN=your-secret-token-here
This same token value must be passed as the `token` argument to changes.watch
when the laptop registers the channel; Google echoes it back in the
X-Goog-Channel-Token header on every push, and we validate it here.

LOGGING
-------
Each accepted notification is appended to ~/.grok/webhook.log with a timestamp
and the headers of interest (X-Goog-Channel-ID, X-Goog-Resource-State,
X-Goog-Resource-ID). No secrets are logged.

RUN
---
    python3 webhook_receiver.py
Binds 0.0.0.0:80; if that fails (e.g. permission denied or in use), falls back
to 0.0.0.0:8080 and logs which port it ended up on.
"""

import http.server
import os
import socketserver
import sys
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
GROK_DIR = os.path.join(HOME, ".grok")
CONF_PATH = os.path.join(GROK_DIR, "webhook.conf")
LOG_PATH = os.path.join(GROK_DIR, "webhook.log")

PRIMARY_PORT = 80
FALLBACK_PORT = 8080
WEBHOOK_PATH = "/webhook"


def _log(line: str) -> None:
    """Append a timestamped line to the webhook log (and echo to stdout)."""
    os.makedirs(GROK_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    msg = f"{stamp} {line}"
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")
    print(msg, flush=True)


def load_token() -> str:
    """Read WEBHOOK_TOKEN from ~/.grok/webhook.conf. Never hardcode the secret."""
    if not os.path.exists(CONF_PATH):
        _log(f"FATAL config file not found: {CONF_PATH} "
             f"(expected a line WEBHOOK_TOKEN=...)")
        sys.exit(1)
    token = None
    with open(CONF_PATH, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("WEBHOOK_TOKEN="):
                token = line.split("=", 1)[1].strip()
    if not token:
        _log(f"FATAL WEBHOOK_TOKEN not set in {CONF_PATH}")
        sys.exit(1)
    return token


EXPECTED_TOKEN = None  # populated in main()


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    # Quieter default logging; we do our own structured logging.
    def log_message(self, fmt, *args):
        return

    def _reject(self, code: int, reason: str) -> None:
        self.send_response(code)
        self.end_headers()
        _log(f"REJECT {code} {reason}")

    def do_POST(self):
        if self.path.rstrip("/") != WEBHOOK_PATH.rstrip("/"):
            self._reject(404, f"unknown path {self.path!r}")
            return

        # Drain the body (Drive sends an empty/short body for most states).
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length:
            try:
                self.rfile.read(length)
            except Exception:
                pass

        token = self.headers.get("X-Goog-Channel-Token", "")
        if token != EXPECTED_TOKEN:
            # Do not log the token values (no secrets in logs).
            self._reject(403, "channel token mismatch")
            return

        channel_id = self.headers.get("X-Goog-Channel-ID", "-")
        resource_state = self.headers.get("X-Goog-Resource-State", "-")
        resource_id = self.headers.get("X-Goog-Resource-ID", "-")
        message_number = self.headers.get("X-Goog-Message-Number", "-")

        # Respond fast: HTTP 204, no body.
        self.send_response(204)
        self.end_headers()

        _log(f"NOTIFY channel_id={channel_id} state={resource_state} "
             f"resource_id={resource_id} msg_no={message_number}")

    def do_GET(self):
        # Simple health check.
        if self.path.rstrip("/") in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        self._reject(404, f"GET not supported for {self.path!r}")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve_on(port: int) -> Server:
    return Server(("0.0.0.0", port), WebhookHandler)


def main() -> None:
    global EXPECTED_TOKEN
    EXPECTED_TOKEN = load_token()

    port = PRIMARY_PORT
    httpd = None
    try:
        httpd = serve_on(PRIMARY_PORT)
    except (PermissionError, OSError) as exc:
        _log(f"WARN could not bind port {PRIMARY_PORT} ({exc}); "
             f"falling back to {FALLBACK_PORT}")
        port = FALLBACK_PORT
        httpd = serve_on(FALLBACK_PORT)

    _log(f"START webhook receiver listening on 0.0.0.0:{port}{WEBHOOK_PATH}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        _log("STOP received KeyboardInterrupt")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
