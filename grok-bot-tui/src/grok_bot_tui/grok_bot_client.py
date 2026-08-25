"""Grok Bot backend via Cursor Connect-RPC. Uses Grok Bot session tokens, not xAI API keys."""

from __future__ import annotations

import base64
import json
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx

DEFAULT_BOT_API = "https://api2.cursor.sh"
GROK_BOT_SERVICE = "aiserver.v1.GrokBotService"


class GrokBotAPIError(Exception):
    """Safe-to-print Grok Bot API error (no tokens)."""


def _json_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return None


def _error_text(body: Any, status: int) -> str:
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            msg = err.get("message") or err.get("code")
            if msg:
                return str(msg)
        if isinstance(err, str) and err:
            return err
        msg = body.get("message")
        if isinstance(msg, str) and msg:
            return msg
    if status == 401:
        return "Grok Bot session expired. Sign in with grok-bot (Gmail), then retry."
    if status == 429:
        return "Rate limited (HTTP 429)."
    if status >= 500:
        return f"Grok Bot server error (HTTP {status})."
    return f"Grok Bot API error (HTTP {status})."


def _b64_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _parse_body(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw and isinstance(raw[0], int):
        try:
            return json.loads(bytes(raw).decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return None
    if isinstance(raw, str) and raw.strip():
        try:
            decoded = base64.b64decode(raw)
            return json.loads(decoded.decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


class GrokBotClient:
    """POST aiserver.v1.GrokBotService methods. Never logs Authorization."""

    def __init__(
        self,
        access_token: str,
        *,
        timeout: float = 120.0,
        base_url: str = DEFAULT_BOT_API,
        client_version: str = "0.24.0",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = "grok-bot"
        self.last_usage: dict[str, int] | None = None
        self.poll_sleep: Callable[[float], None] = time.sleep
        self.poll_interval = 0.7
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Connect-Protocol-Version": "1",
                "Connect-Timeout-Ms": "120000",
                "x-cursor-client-type": "sand",
                "x-cursor-client-version": client_version,
                "x-sand-box-namespace": "prod",
                "x-ghost-mode": "true",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GrokBotClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def rpc(self, method: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._http.post(f"/{GROK_BOT_SERVICE}/{method}", json=body)
        except httpx.TimeoutException as exc:
            raise GrokBotAPIError("Request timed out.") from exc
        except httpx.RequestError as exc:
            raise GrokBotAPIError("Network error. Check connectivity and try again.") from exc
        payload = _json_body(response)
        if response.status_code >= 400:
            raise GrokBotAPIError(_error_text(payload, response.status_code))
        return payload if isinstance(payload, dict) else {}

    def list_transcript(self, agent_id: str, *, limit: int = 80) -> dict[str, Any]:
        return self.rpc(
            "ListGrokBotTranscriptEntries",
            {"agentId": agent_id, "limit": int(limit)},
        )

    def commit_user_message(self, agent_id: str, text: str, *, generation: int, seq: int) -> dict[str, Any]:
        stamp = int(time.time() * 1000)
        entry_id = "tui" + uuid.uuid4().hex[:10]
        body_obj = {
            "kind": "send-message",
            "id": entry_id,
            "message": {"type": "text", "content": text},
            "timestampMs": stamp,
        }
        return self.rpc(
            "CommitGrokBotTranscriptEntries",
            {
                "agentId": agent_id,
                "generation": generation,
                "entries": [
                    {
                        "seq": str(seq),
                        "entryKind": "send-message",
                        "body": _b64_json(body_obj),
                        "updatedSeq": str(seq),
                    }
                ],
            },
        )

    def stream_text(
        self,
        messages: list[dict[str, str]],
        *,
        agent_id: str,
        sleep: Callable[[float], None] | None = None,
        timeout: float = 45.0,
        interval: float | None = None,
    ) -> Iterator[str]:
        """Send the latest user line to the Grok Bot agent and yield reply text."""
        self.last_usage = None
        if not agent_id:
            raise GrokBotAPIError("Select a Grok Bot first.")
        user_text = ""
        for item in reversed(messages):
            if item.get("role") == "user":
                user_text = item.get("content") or ""
                break
        if not user_text.strip():
            raise GrokBotAPIError("Empty message.")
        try:
            self.rpc("EnsureSandBox", {})
        except GrokBotAPIError:
            pass
        listed = self.list_transcript(agent_id)
        generation = int(listed.get("generation") or 1)
        seq = _next_seq(listed.get("entries"))
        before = _assistant_text(listed.get("entries"))
        self.commit_user_message(agent_id, user_text, generation=generation, seq=seq)
        pause = sleep or self.poll_sleep
        gap = self.poll_interval if interval is None else interval
        deadline = time.monotonic() + timeout
        last = before
        while time.monotonic() < deadline:
            pause(gap)
            listed = self.list_transcript(agent_id)
            current = _assistant_text(listed.get("entries"))
            if current.startswith(last) and len(current) > len(last):
                yield current[len(last) :]
                last = current
                if not _still_streaming(listed.get("entries")):
                    return
            elif current != last and current and not current.startswith(last):
                yield current if not last else current[len(last) :] if current.startswith(last) else current
                last = current
                if not _still_streaming(listed.get("entries")):
                    return
            elif last != before and not _still_streaming(listed.get("entries")):
                return
        if last == before:
            raise GrokBotAPIError(
                "Grok Bot did not reply in time. Keep grok-bot signed in so the bot computer is running, then try again."
            )


def _next_seq(entries: Any) -> int:
    best = 0
    if not isinstance(entries, list):
        return 1
    for item in entries:
        if not isinstance(item, dict):
            continue
        for key in ("seq", "updatedSeq", "updated_seq"):
            raw = item.get(key)
            try:
                best = max(best, int(raw))
            except (TypeError, ValueError):
                continue
    return best + 1


def _entry_payload(item: dict[str, Any]) -> dict[str, Any] | None:
    parsed = _parse_body(item.get("body"))
    if parsed:
        return parsed
    kind = str(item.get("entryKind") or item.get("kind") or "")
    if kind:
        return item
    return None


def _assistant_text(entries: Any) -> str:
    if not isinstance(entries, list):
        return ""
    chunks: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        payload = _entry_payload(item)
        if not payload:
            continue
        kind = str(payload.get("kind") or item.get("entryKind") or "")
        role = str(payload.get("role") or "")
        if kind == "message" and role == "assistant":
            text = payload.get("content")
            if isinstance(text, str) and text:
                chunks.append(text)
        elif kind == "message" and not role:
            text = payload.get("content")
            if isinstance(text, str) and text and payload.get("toAgent"):
                chunks.append(text)
    return chunks[-1] if chunks else ""


def _still_streaming(entries: Any) -> bool:
    if not isinstance(entries, list):
        return False
    for item in reversed(entries):
        if not isinstance(item, dict):
            continue
        payload = _entry_payload(item) or item
        if payload.get("isStreaming") is True:
            return True
        if str(payload.get("role") or "") == "assistant" or str(payload.get("kind") or "") == "message":
            return bool(payload.get("isStreaming"))
    return False
