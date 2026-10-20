#!/usr/bin/env python3
"""
heartbeat.py — lightweight liveness/heartbeat probe for the laptop.

Makes ONE trivial outside call (ICMP ping, with a TCP-connect fallback) and
writes a small JSON status file holding exactly three things:
  * method    — the contact method/target actually used (e.g. "ping 1.1.1.1"
                or "tcp 1.1.1.1:443")
  * timestamp — ISO-8601 UTC time of this check
  * status    — the last status message returned, good or bad

No API hammering, no X API, no heavy dependencies (stdlib only).

OUTPUT LOCATION
---------------
The JSON is written to the Drive-synced "Grok" folder so the cloud agent can
read it via Drive. Configurable via the HEARTBEAT_JSON env var; defaults to:
    ~/GoogleDrive/Grok/heartbeat.json
John may instead symlink this path to wherever his Drive client syncs the Grok
folder, e.g.:
    ln -s "$HOME/Insync/jobs4johnm@gmail.com/Google Drive/Grok/heartbeat.json" \\
          "$HOME/GoogleDrive/Grok/heartbeat.json"

NOTE: only lightweight status/JSON belongs in Drive/Grok. The CODE for this
script lives in GitHub (code4johnm/grok_bot_linux, async-index/).

RUN
---
    python3 heartbeat.py
    HEARTBEAT_JSON=/path/to/Grok/heartbeat.json python3 heartbeat.py
    python3 heartbeat.py --target 1.1.1.1 --tcp-port 443
"""

import argparse
import json
import os
import socket
import subprocess
from datetime import datetime, timezone

DEFAULT_JSON = os.path.expanduser(
    os.environ.get("HEARTBEAT_JSON", "~/GoogleDrive/Grok/heartbeat.json")
)
DEFAULT_TARGET = "1.1.1.1"
DEFAULT_TCP_PORT = 443


def try_ping(target: str, timeout: int = 3):
    """Return (ok, message) for a single ICMP ping."""
    try:
        # -c 1 one packet; -W timeout seconds (Linux iputils).
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), target],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=timeout + 2, text=True,
        )
        if proc.returncode == 0:
            # Grab the rtt line if present for a concise status.
            line = next((l.strip() for l in proc.stdout.splitlines()
                         if "time=" in l), "ping ok")
            return True, line
        return False, f"ping failed rc={proc.returncode}"
    except FileNotFoundError:
        return False, "ping binary not found"
    except subprocess.TimeoutExpired:
        return False, "ping timed out"
    except Exception as exc:  # pragma: no cover
        return False, f"ping error: {exc}"


def try_tcp(target: str, port: int, timeout: int = 3):
    """Return (ok, message) for a single TCP connect."""
    try:
        with socket.create_connection((target, port), timeout=timeout):
            return True, f"tcp connect ok to {target}:{port}"
    except Exception as exc:
        return False, f"tcp connect failed to {target}:{port}: {exc}"


def write_status(path: str, method: str, status: str) -> None:
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "method": method,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, path)  # atomic
    print(json.dumps(payload))


def main() -> None:
    parser = argparse.ArgumentParser(description="Lightweight liveness heartbeat")
    parser.add_argument("--target", default=DEFAULT_TARGET,
                        help=f"host/IP to probe (default {DEFAULT_TARGET})")
    parser.add_argument("--tcp-port", type=int, default=DEFAULT_TCP_PORT,
                        help=f"TCP fallback port (default {DEFAULT_TCP_PORT})")
    parser.add_argument("--json", default=DEFAULT_JSON,
                        help=f"status JSON path (default {DEFAULT_JSON})")
    args = parser.parse_args()

    ok, msg = try_ping(args.target)
    if ok:
        write_status(args.json, f"ping {args.target}", msg)
        return
    # Fallback to TCP connect.
    ok, tcp_msg = try_tcp(args.target, args.tcp_port)
    method = f"tcp {args.target}:{args.tcp_port}"
    status = tcp_msg if ok else f"{msg}; {tcp_msg}"
    write_status(args.json, method, status)


if __name__ == "__main__":
    main()
