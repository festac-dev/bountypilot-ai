"""Unit tests for secret redaction."""

from __future__ import annotations

from bountypilot.security.redaction import is_secret_key, redact_mapping, redact_text


def test_secret_keys_detected():
    assert is_secret_key("GIBWORK_API_KEY")
    assert is_secret_key("AI_API_KEY")
    assert is_secret_key("MY_SERVICE_TOKEN")
    assert is_secret_key("DATABASE_PASSWORD")
    assert not is_secret_key("GIBWORK_BASE_URL")
    assert not is_secret_key("LOG_LEVEL")


def test_redact_mapping():
    out = redact_mapping({"GIBWORK_API_KEY": "abc123", "LOG_LEVEL": "DEBUG"})
    assert out["GIBWORK_API_KEY"] == "[REDACTED]"
    assert out["LOG_LEVEL"] == "DEBUG"


def test_redact_text_key_value_pairs():
    text = "config loaded with api_key=hunter2 and other=stuff"
    out = redact_text(text)
    assert "hunter2" not in out
    assert "other=stuff" in out


def test_redact_text_openai_style_keys():
    out = redact_text("using key sk-abcdefghijklmnop123456 today")
    assert "sk-abcdefghijklmnop123456" not in out
    assert "[REDACTED]" in out


def test_redact_text_preserves_normal_content():
    text = "Bounty 1052f22d titled 'Gibwork Developer Hackathon Bounty' retrieved."
    assert redact_text(text) == text
