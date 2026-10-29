#!/usr/bin/env python3
"""Heartbeat for a local copy of the Drive Grok folder.

Stdlib only. Pings 1.1.1.1 (ICMP, then TCP 443). When a bus directory is
present, writes heartbeat.json there and notes new msg-*.yaml files.

This does not execute message text. The desktop agent owns command handling.
This does not replace ~/.grok/heartbeat.py, which pings the LAN gateway.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

PING_HOST = "1.1.1.1"
TCP_PORT = 443
MAIL_TO = "jobs4johnm@gmail.com"
STATE_DIR = Path.home() / ".local" / "state" / "grok-heartbeat"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def icmp_ping(host: str = PING_HOST) -> dict:
    try:
        proc = subprocess.run(
            ["ping", "-c", "1", "-W", "2", host],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "method": "icmp", "detail": type(exc).__name__}
    ok = proc.returncode == 0
    rtt = ""
    for line in (proc.stdout or "").splitlines():
        if "rtt" in line or "round-trip" in line:
            rtt = line.strip()
    return {"ok": ok, "method": "icmp", "rtt": rtt}


def tcp_ping(host: str = PING_HOST, port: int = TCP_PORT) -> dict:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=3):
            elapsed = time.monotonic() - started
        return {"ok": True, "method": "tcp", "port": port, "seconds": round(elapsed, 4)}
    except OSError as exc:
        return {"ok": False, "method": "tcp", "port": port, "detail": type(exc).__name__}


def probe() -> dict:
    icmp = icmp_ping()
    if icmp.get("ok"):
        return {"online": True, "icmp": icmp, "tcp": None}
    tcp = tcp_ping()
    return {"online": bool(tcp.get("ok")), "icmp": icmp, "tcp": tcp}


def bus_dir() -> Path | None:
    candidates = []
    env = os.environ.get("GROK_BUS_DIR", "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    candidates.extend(
        [
            Path.home() / "Grok",
            Path.home() / "Google Drive" / "Grok",
            Path("/mnt/5TB/Grok"),
        ]
    )
    for path in candidates:
        if path.is_dir():
            return path
    return None


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_heartbeat(directory: Path, status: dict) -> Path:
    payload = {
        "checked_at": status["checked_at"],
        "online": status["online"],
        "last_success_at": status.get("last_success_at"),
        "probe": status.get("probe"),
    }
    path = directory / "heartbeat.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def observe_messages(directory: Path, checked_at: str) -> list[str]:
    """Write reply files for new msg-*.yaml names. Do not run their text."""
    seen_path = STATE_DIR / "seen-msgs.json"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    seen = set(_read_json(seen_path).get("names") or [])
    noted: list[str] = []
    for path in sorted(directory.glob("msg-*.yaml")):
        if path.name in seen:
            continue
        reply_name = "reply-" + path.name[len("msg-") :]
        reply = directory / reply_name
        if not reply.exists():
            body = (
                "id: reply-%s\n"
                "from: desktop\n"
                "to: john\n"
                "in_reply_to: %s\n"
                "status: observed\n"
                "handled_by: heartbeat-poller\n"
                "executed: false\n"
                "note: Observed in the heartbeat cycle. The desktop agent owns execution.\n"
                "checked_at: %s\n"
            ) % (path.stem[len("msg-") :], path.name, checked_at)
            reply.write_text(body, encoding="utf-8")
        seen.add(path.name)
        noted.append(path.name)
    seen_path.write_text(json.dumps({"names": sorted(seen)}, indent=2) + "\n", encoding="utf-8")
    return noted


def maybe_daily_mail(status: dict) -> dict:
    """One local summary per UTC day. No stored token. Skip when sendmail is absent."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = STATE_DIR / "mail-state.json"
    today = status["checked_at"][:10]
    previous = _read_json(stamp)
    if previous.get("sent_on") == today:
        return {"sent": False, "reason": "already_sent_today"}
    sendmail = Path("/usr/sbin/sendmail")
    if not sendmail.is_file():
        return {"sent": False, "reason": "no_local_sendmail"}
    online = "online" if status.get("online") else "offline"
    last = status.get("last_success_at") or "none"
    msg = EmailMessage()
    msg["To"] = MAIL_TO
    msg["From"] = MAIL_TO
    msg["Subject"] = "Desktop heartbeat %s %s" % (today, online)
    msg.set_content(
        "Desktop is %s.\nLast successful heartbeat: %s\nChecked at: %s\n"
        % (online, last, status["checked_at"])
    )
    try:
        proc = subprocess.run(
            [str(sendmail), "-t"],
            input=msg.as_string(),
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"sent": False, "reason": type(exc).__name__}
    if proc.returncode != 0:
        return {"sent": False, "reason": "sendmail_exit_%s" % proc.returncode}
    stamp.write_text(json.dumps({"sent_on": today, "last_success_at": last}) + "\n", encoding="utf-8")
    return {"sent": True, "reason": "sent"}


def main() -> int:
    checked_at = _now()
    probe_result = probe()
    state_path = STATE_DIR / "last-success.json"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    previous = _read_json(state_path)
    last_success = previous.get("last_success_at")
    if probe_result["online"]:
        last_success = checked_at
        state_path.write_text(json.dumps({"last_success_at": last_success}) + "\n", encoding="utf-8")
    status = {
        "checked_at": checked_at,
        "online": probe_result["online"],
        "last_success_at": last_success,
        "probe": probe_result,
    }
    directory = bus_dir()
    if directory is None:
        status["bus_dir"] = "absent"
        status["messages"] = []
    else:
        status["bus_dir"] = str(directory)
        write_heartbeat(directory, status)
        status["messages"] = observe_messages(directory, checked_at)
    status["mail"] = maybe_daily_mail(status)
    print(json.dumps({k: status[k] for k in ("checked_at", "online", "bus_dir", "mail", "last_success_at")}))
    return 0 if probe_result["online"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
