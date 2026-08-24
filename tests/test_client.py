from __future__ import annotations

import urllib.error
from io import BytesIO

import pytest

from grok_bot.client import GrokAPIError, extract_reply, send_prompt
from grok_bot.config import Settings
from tests.conftest import grok_payload


def test_extract_reply_reads_chat_completions_shape() -> None:
    assert extract_reply(grok_payload("hi")) == "hi"


def test_extract_reply_rejects_bad_payload() -> None:
    with pytest.raises(GrokAPIError):
        extract_reply({"choices": []})


def test_send_prompt_posts_to_xai(captured_request) -> None:
    reply = send_prompt(
        "ping",
        "secret-key",
        Settings(api_base="https://api.x.ai/v1", model="grok-4"),
        opener=captured_request["opener"],
    )
    assert reply == "ok"
    assert captured_request["url"] == "https://api.x.ai/v1/chat/completions"
    assert captured_request["headers"]["authorization"] == "Bearer secret-key"
    assert captured_request["body"] == {
        "model": "grok-4",
        "messages": [{"role": "user", "content": "ping"}],
    }


def test_send_prompt_rejects_empty() -> None:
    with pytest.raises(GrokAPIError, match="empty"):
        send_prompt("   ", "key")


def test_send_prompt_http_error() -> None:
    def opener(request, timeout=120):  # noqa: ARG001
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"error":"bad key"}'),
        )

    with pytest.raises(GrokAPIError, match="HTTP 401"):
        send_prompt("hi", "bad", opener=opener)


def test_send_prompt_non_json() -> None:
    class Bad:
        def read(self) -> bytes:
            return b"not-json"

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return None

    with pytest.raises(GrokAPIError, match="non-JSON"):
        send_prompt("hi", "key", opener=lambda *_a, **_k: Bad())
