"""Test configuration module."""
import os
import pytest
from pydantic import ValidationError


def test_config_loads_from_env(monkeypatch):
    """Test that config loads from environment variables."""
    monkeypatch.setenv("MYSQL_HOST", "test-host")
    monkeypatch.setenv("MYSQL_PORT", "3307")
    monkeypatch.setenv("MYSQL_USER", "test-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "test-pass")
    monkeypatch.setenv("MYSQL_DATABASE", "test-db")

    # Clear the cache and import after setting env vars
    from core.config import get_settings
    get_settings.cache_clear()

    from core.config import settings

    assert settings.MYSQL_HOST == "test-host"
    assert settings.MYSQL_PORT == 3307
    assert settings.MYSQL_USER == "test-user"


def test_config_has_defaults():
    """Test that config has sensible defaults."""
    # Clear the cache to get fresh settings
    from core.config import get_settings
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.MYSQL_PORT == 3306
    assert settings.REDIS_PORT == 6379
