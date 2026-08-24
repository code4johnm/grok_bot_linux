from __future__ import annotations

from grok_bot import __version__
from grok_bot.cli import main
from grok_bot.workspace import Workspace


def test_version(capsys) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_status_without_key(workspace_dir, monkeypatch, capsys) -> None:
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "api_key: missing" in out
    assert str(workspace_dir) in out
    assert "xai-" not in out
    assert "sk-" not in out


def test_ask_prints_reply(workspace_dir, monkeypatch, capsys) -> None:
    monkeypatch.setenv("XAI_API_KEY", "test-key-not-real")

    def fake_send(prompt, api_key, settings=None, opener=None):  # noqa: ARG001
        assert prompt == "What is 2+2?"
        assert api_key == "test-key-not-real"
        return "two plus two is four"

    monkeypatch.setattr("grok_bot.cli.send_prompt", fake_send)
    assert main(["ask", "What is 2+2?"]) == 0
    assert capsys.readouterr().out.strip() == "two plus two is four"
    ws = Workspace.open(workspace_dir)
    assert ws.history_count() == 1


def test_ask_missing_key(workspace_dir, monkeypatch, capsys) -> None:
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert main(["ask", "hello"]) == 3
    assert "GROK_API_KEY or XAI_API_KEY" in capsys.readouterr().err


def test_ask_empty_prompt(capsys) -> None:
    assert main(["ask", "   "]) == 2
    assert "empty" in capsys.readouterr().err
