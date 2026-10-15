"""Unit tests for configuration precedence, validation and redaction."""

from __future__ import annotations

import pytest

from bountypilot import constants
from bountypilot.exceptions import ConfigurationError
from bountypilot.settings import load_settings, set_setting


def test_defaults_without_any_source(monkeypatch, tmp_path):
    for key in constants.CONFIG_KEY_NAMES:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("BOUNTYPILOT_DATA_DIRECTORY", raising=False)
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    assert settings.values["GIBWORK_BASE_URL"] == "https://api.gib.work"
    assert settings.values["AI_PROVIDER"] == "local"
    assert settings.gibwork_timeout == 20.0


def test_environment_overrides_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("GIBWORK_TIMEOUT_SECONDS", "33")
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    assert settings.gibwork_timeout == 33.0
    assert settings.sources["GIBWORK_TIMEOUT_SECONDS"] == "environment"


def test_cli_overrides_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("GIBWORK_TIMEOUT_SECONDS", "33")
    settings = load_settings(overrides={"GIBWORK_TIMEOUT_SECONDS": 11}, data_directory=tmp_path, load_dotenv=False)
    assert settings.gibwork_timeout == 11.0
    assert settings.sources["GIBWORK_TIMEOUT_SECONDS"] == "command line"


def test_config_file_persisted_and_loaded(tmp_path, monkeypatch):
    for key in constants.CONFIG_KEY_NAMES:
        monkeypatch.delenv(key, raising=False)
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    set_setting(settings, "LOG_LEVEL", "debug")
    reloaded = load_settings(data_directory=tmp_path, load_dotenv=False)
    assert reloaded.values["LOG_LEVEL"] == "DEBUG"
    assert "config file" in reloaded.sources["LOG_LEVEL"]


def test_invalid_values_rejected(tmp_path):
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    with pytest.raises(ConfigurationError):
        set_setting(settings, "GIBWORK_TIMEOUT_SECONDS", "not-a-number")
    with pytest.raises(ConfigurationError):
        set_setting(settings, "GIBWORK_TIMEOUT_SECONDS", "999")
    with pytest.raises(ConfigurationError):
        set_setting(settings, "AI_PROVIDER", "magic")
    with pytest.raises(ConfigurationError):
        set_setting(settings, "TOTALLY_UNKNOWN", "x")


def test_secret_redaction_in_show(monkeypatch, tmp_path):
    monkeypatch.delenv("GIBWORK_API_KEY", raising=False)
    settings = load_settings(data_directory=tmp_path, load_dotenv=False)
    set_setting(settings, "GIBWORK_API_KEY", "super-secret-value")
    reloaded = load_settings(data_directory=tmp_path, load_dotenv=False)
    redacted = reloaded.as_redacted_dict()
    assert redacted["GIBWORK_API_KEY"] == "[REDACTED]"
    assert "super-secret-value" not in json_dumps(redacted)
    # The real value is still usable internally.
    assert reloaded.gibwork_api_key == "super-secret-value"


def json_dumps(mapping) -> str:
    import json

    return json.dumps(mapping)
