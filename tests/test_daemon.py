from __future__ import annotations

import threading
import time

import pytest

from grok_bot.daemon import Daemon, call_daemon, handle_request, is_daemon_running
from grok_bot.workspace import Workspace


def test_handle_request_ask() -> None:
    out = handle_request({"cmd": "ask", "prompt": "hi"}, lambda p: f"echo:{p}")
    assert out == {"ok": True, "reply": "echo:hi"}


def test_handle_request_unknown() -> None:
    out = handle_request({"cmd": "nope"}, lambda _p: "")
    assert out["ok"] is False


def test_daemon_ask_over_socket(tmp_path) -> None:
    ws = Workspace.open(tmp_path / "ws")
    daemon = Daemon(ws, ask=lambda prompt: f"mock:{prompt}")
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()
    deadline = time.time() + 3
    while time.time() < deadline and not ws.socket_path.exists():
        time.sleep(0.02)
    assert ws.socket_path.exists()
    assert is_daemon_running(ws)
    response = call_daemon(ws, {"cmd": "ask", "prompt": "hello"}, timeout=5)
    assert response == {"ok": True, "reply": "mock:hello"}
    assert ws.history_count() == 1
    daemon.stop()
    thread.join(timeout=3)
