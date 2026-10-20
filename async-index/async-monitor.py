#!/usr/bin/env python3
"""
async-monitor.py — push-driven (and fallback poll/watch) index monitor for the
cloud <-> laptop agent architecture, built around the Drive "Grok" folder.

It processes new msg-*.yaml files addressed to the local agent and writes a
reply-*.yaml acknowledging receipt (echoing the message id and the local path
where it was seen, plus a timestamp). It is idempotent: processed message ids
are tracked in ~/.grok/processed-ids.txt so a message is never acted on twice.

TWO MODES
---------
  --watch-folder   (FALLBACK, recommended when you have no verified HTTPS domain)
      Watches the locally Drive-synced "Grok" folder for new/changed msg-*.yaml.
      Uses inotify if available (pip install inotify_simple) and otherwise a
      short polling loop. Requires NO open port and NO Changes API. This is the
      mode to use with the Google Drive desktop sync client.

  --changes-api    (requires the laptop's own Google credentials)
      Calls Drive changes.list with a saved page token (read from
      channel-config.yaml in the Grok folder), processes new/changed Grok files,
      and advances the stored page token. Requires:
        pip install google-api-python-client google-auth google-auth-oauthlib
      and valid OAuth creds for the jobs4johnm@gmail.com account on the laptop.
      NOTE: changes.watch / changes.getStartPageToken / changes.list are NOT
      available through Creator Bot's connector; they must run here on the
      laptop with the laptop's creds.

NO deletions are ever performed. No secrets are written to logs or replies.

USAGE
-----
  python3 async-monitor.py --watch-folder [--grok-dir ~/GoogleDrive/Grok] [--interval 10]
  python3 async-monitor.py --changes-api  [--grok-dir ~/GoogleDrive/Grok]

The "to" field of a message is matched against --agent-name (default "laptop";
"all"/"*" also match). Adjust with --agent-name if your local agent uses a
different handle.
"""

import argparse
import glob
import os
import sys
import time
import uuid
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
GROK_STATE_DIR = os.path.join(HOME, ".grok")
PROCESSED_PATH = os.path.join(GROK_STATE_DIR, "processed-ids.txt")
LOG_PATH = os.path.join(GROK_STATE_DIR, "async-monitor.log")

DEFAULT_GROK_DIR = os.path.join(HOME, "GoogleDrive", "Grok")


# --------------------------------------------------------------------------- #
# Minimal dependency-free YAML reading/writing for our flat msg-*.yaml schema.
# Messages are simple "key: value" documents (id, from, to, text). We avoid a
# hard PyYAML dependency; if PyYAML is present we use it, else a tiny parser.
# --------------------------------------------------------------------------- #
try:
    import yaml  # type: ignore

    def load_yaml(path):
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def dump_yaml(data):
        return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)

except Exception:  # pragma: no cover - fallback parser
    def load_yaml(path):
        data = {}
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                if not line or line.lstrip().startswith("#") or ":" not in line:
                    continue
                key, val = line.split(":", 1)
                data[key.strip()] = val.strip().strip('"').strip("'")
        return data

    def dump_yaml(data):
        out = []
        for key, val in data.items():
            sval = str(val).replace("\n", " ")
            if any(c in sval for c in ":#\"'") or sval == "":
                sval = '"' + sval.replace('"', '\\"') + '"'
            out.append(f"{key}: {sval}")
        return "\n".join(out) + "\n"


def log(line: str) -> None:
    os.makedirs(GROK_STATE_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    msg = f"{stamp} {line}"
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")
    print(msg, flush=True)


def load_processed() -> set:
    if not os.path.exists(PROCESSED_PATH):
        return set()
    with open(PROCESSED_PATH, "r", encoding="utf-8") as fh:
        return {ln.strip() for ln in fh if ln.strip()}


def mark_processed(msg_id: str) -> None:
    os.makedirs(GROK_STATE_DIR, exist_ok=True)
    with open(PROCESSED_PATH, "a", encoding="utf-8") as fh:
        fh.write(msg_id + "\n")


def addressed_to_us(msg: dict, agent_name: str) -> bool:
    to = str(msg.get("to", "")).strip().lower()
    return to in (agent_name.lower(), "all", "*", "")


def write_reply(grok_dir: str, msg: dict, seen_path: str, agent_name: str) -> str:
    stamp = datetime.now(timezone.utc)
    reply_id = f"reply-{stamp.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
    reply = {
        "id": reply_id,
        "from": agent_name,
        "to": msg.get("from", "cloud"),
        "in_reply_to": msg.get("id", "unknown"),
        "text": (f"ACK received msg id={msg.get('id', 'unknown')} "
                 f"seen at local path {seen_path}"),
        "timestamp": stamp.isoformat(),
    }
    out_path = os.path.join(grok_dir, reply_id + ".yaml")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(dump_yaml(reply))
    log(f"REPLY wrote {out_path} (in_reply_to={msg.get('id')})")
    return out_path


def process_msg_file(path: str, grok_dir: str, processed: set,
                     agent_name: str) -> None:
    try:
        msg = load_yaml(path)
    except Exception as exc:
        log(f"WARN could not parse {path}: {exc}")
        return
    msg_id = str(msg.get("id", "")).strip()
    if not msg_id:
        log(f"SKIP {path} has no id field")
        return
    if msg_id in processed:
        return
    if not addressed_to_us(msg, agent_name):
        log(f"SKIP {path} not addressed to {agent_name} (to={msg.get('to')!r})")
        # Still mark processed so we don't re-evaluate forever.
        processed.add(msg_id)
        mark_processed(msg_id)
        return
    log(f"PROCESS {path} id={msg_id} from={msg.get('from')!r}")
    write_reply(grok_dir, msg, path, agent_name)
    processed.add(msg_id)
    mark_processed(msg_id)


def scan_once(grok_dir: str, processed: set, agent_name: str) -> None:
    pattern = os.path.join(grok_dir, "msg-*.yaml")
    for path in sorted(glob.glob(pattern)):
        process_msg_file(path, grok_dir, processed, agent_name)


# --------------------------------------------------------------------------- #
# Watch-folder (fallback) mode
# --------------------------------------------------------------------------- #
def run_watch_folder(grok_dir: str, interval: float, agent_name: str) -> None:
    grok_dir = os.path.expanduser(grok_dir)
    if not os.path.isdir(grok_dir):
        log(f"FATAL grok dir does not exist: {grok_dir}")
        sys.exit(1)
    processed = load_processed()
    log(f"START watch-folder mode dir={grok_dir} agent={agent_name}")
    # Process whatever is already there first.
    scan_once(grok_dir, processed, agent_name)

    # Prefer inotify if available; fall back to polling.
    try:
        from inotify_simple import INotify, flags  # type: ignore
        inotify = INotify()
        watch_flags = flags.CREATE | flags.MOVED_TO | flags.CLOSE_WRITE
        inotify.add_watch(grok_dir, watch_flags)
        log("watch backend: inotify")
        while True:
            for _event in inotify.read(timeout=int(interval * 1000)):
                pass  # any event -> rescan (cheap, idempotent)
            scan_once(grok_dir, processed, agent_name)
    except Exception as exc:
        log(f"watch backend: polling every {interval}s (inotify unavailable: {exc})")
        while True:
            time.sleep(interval)
            scan_once(grok_dir, processed, agent_name)


# --------------------------------------------------------------------------- #
# Changes API mode (requires laptop Google creds)
# --------------------------------------------------------------------------- #
def run_changes_api(grok_dir: str, agent_name: str) -> None:
    """
    Push-driven processing via Drive changes.list.

    Flow (runs on the laptop with its own OAuth creds):
      1. Read page_token from channel-config.yaml (in the Grok folder).
      2. changes.list(pageToken=...) -> changed files.
      3. For changed files in the Grok folder, download + process msg-*.yaml.
      4. Save newStartPageToken back to channel-config.yaml.

    This function is intentionally guarded: it requires
    google-api-python-client and valid credentials, neither of which Creator
    Bot (cloud) has. Fill in creds loading for your laptop's setup.
    """
    grok_dir = os.path.expanduser(grok_dir)
    cfg_path = os.path.join(grok_dir, "channel-config.yaml")
    if not os.path.exists(cfg_path):
        log(f"FATAL channel-config.yaml not found at {cfg_path}. "
            f"Register the watch channel first (see README-grok-agent.md).")
        sys.exit(1)
    try:
        cfg = load_yaml(cfg_path)
    except Exception as exc:
        log(f"FATAL could not read {cfg_path}: {exc}")
        sys.exit(1)

    page_token = str(cfg.get("page_token", "")).strip()
    if not page_token or page_token.startswith("<"):
        log("FATAL page_token missing/placeholder in channel-config.yaml. "
            "Run changes.getStartPageToken on the laptop and fill it in.")
        sys.exit(1)

    try:
        from googleapiclient.discovery import build  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
    except Exception as exc:
        log("FATAL google-api-python-client not installed. "
            "pip install google-api-python-client google-auth "
            f"google-auth-oauthlib ({exc})")
        sys.exit(1)

    # --- Credential loading is laptop-specific; provide your token path. ------
    creds_path = os.path.join(GROK_STATE_DIR, "drive-token.json")
    if not os.path.exists(creds_path):
        log(f"FATAL OAuth token not found at {creds_path}. "
            "Provide the laptop's Drive creds (jobs4johnm@gmail.com).")
        sys.exit(1)
    creds = Credentials.from_authorized_user_file(creds_path)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)

    processed = load_processed()
    log(f"START changes-api mode grok_dir={grok_dir} agent={agent_name}")

    resp = service.changes().list(
        pageToken=page_token,
        spaces="drive",
        fields="newStartPageToken,nextPageToken,"
               "changes(fileId,removed,file(id,name,parents,mimeType))",
    ).execute()

    for change in resp.get("changes", []):
        if change.get("removed"):
            continue
        f = change.get("file") or {}
        name = f.get("name", "")
        if not name.startswith("msg-") or not name.endswith(".yaml"):
            continue
        # NOTE: this processes by syncing the file locally; simplest path is to
        # rely on the Drive desktop client having written it into grok_dir, so
        # we hand off to the same local processor.
        local_path = os.path.join(grok_dir, name)
        if os.path.exists(local_path):
            process_msg_file(local_path, grok_dir, processed, agent_name)
        else:
            log(f"NOTE change for {name} not yet present locally at {local_path}")

    new_token = resp.get("newStartPageToken") or resp.get("nextPageToken")
    if new_token:
        cfg["page_token"] = new_token
        with open(cfg_path, "w", encoding="utf-8") as fh:
            fh.write(dump_yaml(cfg))
        log(f"advanced page_token -> {new_token}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Grok cloud<->laptop index monitor")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--watch-folder", action="store_true",
                      help="Fallback: watch the locally Drive-synced Grok folder")
    mode.add_argument("--changes-api", action="store_true",
                      help="Push-driven via Drive changes.list (needs laptop creds)")
    parser.add_argument("--grok-dir", default=DEFAULT_GROK_DIR,
                        help=f"Local Drive-synced Grok folder (default {DEFAULT_GROK_DIR})")
    parser.add_argument("--interval", type=float, default=10.0,
                        help="Poll interval seconds for watch-folder fallback")
    parser.add_argument("--agent-name", default="laptop",
                        help="This agent's handle for matching msg 'to' field")
    args = parser.parse_args()

    if args.watch_folder:
        run_watch_folder(args.grok_dir, args.interval, args.agent_name)
    else:
        run_changes_api(args.grok_dir, args.agent_name)


if __name__ == "__main__":
    main()
