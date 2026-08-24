from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_matches_tree() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in (
        "src/grok_bot/",
        "tests/",
        "bin/grok-bot",
        "install.sh",
        "Makefile",
        "systemd/",
        "requirements.txt",
        "make test",
        "make install",
        "GROK_API_KEY",
        "XAI_API_KEY",
    ):
        assert name in readme
    lowered = readme.lower()
    assert "kali package" not in lowered
    assert "official xai or grok desktop" in lowered
    assert "not an official" in lowered


def test_repo_has_no_secret_files() -> None:
    forbidden_names = {".env", "grok-bot.env", "secrets.txt", "id_rsa"}
    found = [
        path
        for path in ROOT.rglob("*")
        if ".git" not in path.parts and path.name in forbidden_names
    ]
    assert found == []
