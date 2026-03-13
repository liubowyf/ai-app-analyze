"""Test configuration module."""
import json
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
    from core.config import cached_settings
    cached_settings.cache_clear()

    settings = cached_settings()

    assert settings.MYSQL_HOST == "test-host"
    assert settings.MYSQL_PORT == 3307
    assert settings.MYSQL_USER == "test-user"


def test_config_has_defaults():
    """Test that config has sensible defaults."""
    # Clear the cache to get fresh settings
    from core.config import cached_settings
    cached_settings.cache_clear()

    settings = cached_settings()

    assert settings.MYSQL_PORT == 3306
    assert settings.REDIS_PORT == 6379


def test_config_builds_authenticated_redis_url_from_split_password(monkeypatch):
    """Split broker password should be folded into REDIS_BROKER_URL."""
    monkeypatch.setenv("REDIS_BROKER_URL", "redis://10.0.0.8:6379/1")
    monkeypatch.setenv("REDIS_PASSWORD", "s3cret@value")

    from core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.REDIS_BROKER_URL == "redis://:s3cret%40value@10.0.0.8:6379/1"
    assert settings.REDIS_PORT == 6379


def test_config_supports_legacy_lowercase_password_alias(monkeypatch):
    """Legacy lowercase password entry in .env should still authenticate Redis."""
    monkeypatch.setenv("REDIS_BROKER_URL", "redis://10.0.0.9:6379/2")
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.setenv("password", "legacy-secret")

    from core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.REDIS_BROKER_URL == "redis://:legacy-secret@10.0.0.9:6379/2"


def test_config_preserves_embedded_redis_credentials(monkeypatch):
    """Already-authenticated broker URLs should not be rewritten."""
    monkeypatch.setenv("REDIS_BROKER_URL", "redis://:embedded%21secret@10.0.0.10:6379/3")
    monkeypatch.setenv("REDIS_PASSWORD", "ignored")

    from core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.REDIS_BROKER_URL == "redis://:embedded%21secret@10.0.0.10:6379/3"


def test_config_defaults_analysis_backend_to_redroid_remote(monkeypatch):
    """Analysis backend should default to the redroid remote path."""
    monkeypatch.delenv("ANALYSIS_BACKEND", raising=False)

    from core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.ANALYSIS_BACKEND == "redroid_remote"


def test_config_accepts_redroid_remote_analysis_backend(monkeypatch):
    """Analysis backend should support the redroid remote adapter."""
    monkeypatch.setenv("ANALYSIS_BACKEND", "redroid_remote")

    from core.config import Settings

    settings = Settings(_env_file=None)

    assert settings.ANALYSIS_BACKEND == "redroid_remote"


def test_config_rejects_unknown_analysis_backend(monkeypatch):
    """Analysis backend should be constrained to known adapters."""
    monkeypatch.setenv("ANALYSIS_BACKEND", "unsupported_backend")

    from core.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_config_parses_redroid_slots_json(monkeypatch):
    monkeypatch.setenv(
        "REDROID_SLOTS_JSON",
        json.dumps(
            [
                {"name": "redroid-1", "adb_serial": "61.152.73.88:16555", "container_name": "redroid-1"},
                {"name": "redroid-2", "adb_serial": "61.152.73.88:16556", "container_name": "redroid-2"},
                {"name": "redroid-3", "adb_serial": "61.152.73.88:16557", "container_name": "redroid-3"},
            ]
        ),
    )

    from core.config import Settings

    settings = Settings(_env_file=None)

    assert [slot["name"] for slot in settings.redroid_slots] == ["redroid-1", "redroid-2", "redroid-3"]
    assert settings.redroid_slots[2]["adb_serial"] == "61.152.73.88:16557"
