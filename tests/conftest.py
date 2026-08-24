from __future__ import annotations

import json
import pytest


class FakeHTTPResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeHTTPResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def grok_payload(text: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


@pytest.fixture
def captured_request():
    seen: dict = {}

    def opener(request, timeout=120):
        seen["url"] = request.full_url
        seen["headers"] = {k.lower(): v for k, v in request.header_items()}
        seen["body"] = json.loads(request.data.decode("utf-8"))
        seen["timeout"] = timeout
        return FakeHTTPResponse(grok_payload("ok"))

    seen["opener"] = opener
    return seen


@pytest.fixture
def workspace_dir(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    monkeypatch.setenv("GROK_BOT_WORKSPACE", str(root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return root
