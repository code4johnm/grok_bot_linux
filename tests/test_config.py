from __future__ import annotations

import pytest

from grok_bot.config import ConfigError, Settings, api_key_present, read_api_key


def test_prefers_grok_api_key() -> None:
    env = {"GROK_API_KEY": "from-grok", "XAI_API_KEY": "from-xai"}
    assert read_api_key(env) == "from-grok"


def test_falls_back_to_xai_api_key() -> None:
    assert read_api_key({"XAI_API_KEY": "from-xai"}) == "from-xai"


def test_missing_key_raises() -> None:
    with pytest.raises(ConfigError, match="GROK_API_KEY or XAI_API_KEY"):
        read_api_key({})


def test_api_key_present() -> None:
    assert api_key_present({"GROK_API_KEY": "x"}) is True
    assert api_key_present({}) is False


def test_settings_from_env() -> None:
    settings = Settings.from_env(
        {
            "GROK_API_BASE": "https://example.test/v1",
            "GROK_MODEL": "grok-3",
            "GROK_TIMEOUT": "9",
        }
    )
    assert settings.api_base == "https://example.test/v1"
    assert settings.model == "grok-3"
    assert settings.timeout == 9.0
