"""Tests for SettingsResponse — masking happens at the model boundary."""
import pytest
from routes.admin import SettingsResponse


def test_sensitive_key_is_masked():
    data = {"AI_API": {"type": "gemini", "key": "AIzaSy_supersecretvalue1234"}}
    result = SettingsResponse.model_validate(data)
    section = result.model_dump()["AI_API"]
    assert section["key"].startswith("•••••")
    assert section["key"].endswith("1234")
    assert "supersecret" not in section["key"]


def test_non_sensitive_field_passes_through():
    data = {"AI_API": {"type": "gemini", "model": "gemini-2.5-flash", "key": "abcdefghijklmnop"}}
    result = SettingsResponse.model_validate(data)
    section = result.model_dump()["AI_API"]
    assert section["type"] == "gemini"
    assert section["model"] == "gemini-2.5-flash"


def test_short_key_still_masked():
    data = {"AI_API": {"key": "abc"}}
    result = SettingsResponse.model_validate(data)
    assert result.model_dump()["AI_API"]["key"] == "•••••"
