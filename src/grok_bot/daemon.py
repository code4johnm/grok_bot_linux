"""Local daemon: Unix socket, workspace history, one JSON request per connection."""

from __future__ import annotations

import json
import os
import signal
import socket
import threading
from typing import Any, Callable

from grok_bot.client import GrokAPIError, send_prompt
from grok_bot.config import Settings, read_api_key
from grok_bot.workspace import Workspace

AskFn = Callable[[str], str]


def _recv_json(conn: socket.socket, limit: int = 1_000_000) -> dict[str, Any]:
    chunks: list[bytes] = []
    received = 0
    while received < limit:
        piece = conn.recv(4096)
        if not piece:
            break
        chunks.append(piece)
        received += len(piece)
        if b"\n" in piece:
            break
    if not chunks:
        raise ValueError("empty request")
    text = b"".join(chunks).decode("utf-8").strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("request must be a JSON object")
    return payload


def _send_json(conn: socket.socket, payload: dict[str, Any]) -> None:
    conn.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


def handle_request(payload: dict[str, Any], ask: AskFn) -> dict[str, Any]:
    cmd = str(payload.get("cmd", "")).strip()
    if cmd == "ping":
        return {"ok": True, "reply": "pong"}
    if cmd == "status":
        return {"ok": True, "reply": "running"}
    if cmd != "ask":
        return {"ok": False, "error": f"unknown cmd: {cmd or '(missing)'}"}
    prompt = payload.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        return {"ok": False, "error": "prompt is required"}
    try:
        reply = ask(prompt)
    except (GrokAPIError, OSError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "reply": reply}


def is_daemon_running(workspace: Workspace) -> bool:
    pid = workspace.read_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return workspace.socket_path.exists()


def call_daemon(workspace: Workspace, payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(workspace.socket_path))
        sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            piece = sock.recv(4096)
            if not piece:
                break
            chunks.append(piece)
            if b"\n" in piece:
                break
    finally:
        sock.close()
    text = b"".join(chunks).decode("utf-8").strip()
    response = json.loads(text)
    if not isinstance(response, dict):
        raise GrokAPIError("daemon returned a non-object")
    return response


class Daemon:
    def __init__(
        self,
        workspace: Workspace,
        settings: Settings | None = None,
        ask: AskFn | None = None,
        api_key: str | None = None,
    ) -> None:
        self.workspace = workspace
        self.settings = settings or Settings.from_env()
        self._ask = ask
        self._api_key = api_key
        self._stop = threading.Event()
        self._server: socket.socket | None = None

    def _ask_api(self, prompt: str) -> str:
        if self._ask is not None:
            reply = self._ask(prompt)
        else:
            key = self._api_key if self._api_key is not None else read_api_key()
            reply = send_prompt(prompt, key, self.settings)
        self.workspace.append_history(prompt, reply)
        return reply

    def serve_forever(self) -> None:
        self.workspace.root.mkdir(parents=True, exist_ok=True)
        if self.workspace.socket_path.exists():
            self.workspace.socket_path.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self.workspace.socket_path))
        self.workspace.socket_path.chmod(0o600)
        server.listen(16)
        server.settimeout(0.5)
        self._server = server
        self.workspace.write_pid(os.getpid())

        def _stop_signal(_signum: int, _frame: Any) -> None:
            self._stop.set()

        try:
            signal.signal(signal.SIGTERM, _stop_signal)
            signal.signal(signal.SIGINT, _stop_signal)
        except ValueError:
            # Threads (tests) cannot install signal handlers.
            pass
        try:
            while not self._stop.is_set():
                try:
                    conn, _ = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                threading.Thread(target=self._serve_one, args=(conn,), daemon=True).start()
        finally:
            server.close()
            self.workspace.clear_runtime_files()

    def _serve_one(self, conn: socket.socket) -> None:
        try:
            payload = _recv_json(conn)
            _send_json(conn, handle_request(payload, self._ask_api))
        except Exception as exc:  # noqa: BLE001 — socket handler must stay up
            try:
                _send_json(conn, {"ok": False, "error": str(exc)})
            except OSError:
                pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        self._stop.set()
        if self._server is not None:
            try:
                self._server.close()
            except OSError:
                pass
