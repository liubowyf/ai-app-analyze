"""Configuration management using Pydantic Settings."""
from functools import lru_cache
from urllib.parse import quote, urlparse, urlunsplit
from typing import ClassVar

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    ANALYSIS_BACKEND_ALLOWED: ClassVar[set[str]] = {"redroid_remote"}

    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "apk_analysis"

    # MinIO Configuration
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "apk-analysis"
    MINIO_SECURE: bool = False

    # AI Model Configuration
    AI_BASE_URL: str = "http://10.16.148.66:6000/v1"
    AI_MODEL_NAME: str = "/models/AutoGLM-Phone"
    AI_API_KEY: str = "EMPTY"
    AI_MAX_TOKENS: int = 3000
    AI_TEMPERATURE: float = 0.1

    # API Configuration
    API_TOKEN: str = ""
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Task Queue Configuration (Dramatiq + Redis)
    TASK_BACKEND: str = "dramatiq"
    ANALYSIS_BACKEND: str = "redroid_remote"
    REDIS_BROKER_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: str = Field(default="", validation_alias=AliasChoices("REDIS_PASSWORD", "password"))
    TASK_ACTOR_LOCK_TTL_SECONDS: int = 300
    TASK_ACTOR_RETRY_BACKOFF_SECONDS: str = "10,30,60"
    TRAFFIC_PROXY_PORT_START: int = 18080
    TRAFFIC_PROXY_PORT_END: int = 18129
    TRAFFIC_PROXY_LEASE_TTL_SECONDS: int = 3900
    REDROID_ADB_SERIAL: str = "<host-agent-node>:16555"
    REDROID_SSH_HOST: str = "<host-agent-node>"
    REDROID_SSH_PORT: int = 22
    REDROID_SSH_USER: str = ""
    REDROID_SSH_KEY_PATH: str = ""
    REDROID_SSH_PASSWORD: str = ""
    REDROID_CONTAINER_NAME: str = "redroid-1"
    REDROID_CAPTURE_SECONDS: int = 120

    @model_validator(mode="after")
    def apply_redis_password(self) -> "Settings":
        """Fold split Redis password into broker URL when auth is omitted."""
        broker_url = (self.REDIS_BROKER_URL or "").strip()
        password = (self.REDIS_PASSWORD or "").strip()
        if not broker_url or not password:
            return self

        parsed = urlparse(broker_url)
        if parsed.password:
            return self

        encoded_password = quote(password, safe="")
        hostname = parsed.hostname or ""
        if not hostname:
            return self

        auth = parsed.username or ""
        netloc = f"{auth}:{encoded_password}@{hostname}"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        self.REDIS_BROKER_URL = urlunsplit(
            (
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.query,
                parsed.fragment,
            )
        )
        return self

    @model_validator(mode="after")
    def validate_analysis_backend(self) -> "Settings":
        """Keep analysis backend constrained to known implementations."""
        backend = (self.ANALYSIS_BACKEND or "").strip()
        if backend not in self.ANALYSIS_BACKEND_ALLOWED:
            allowed = ", ".join(sorted(self.ANALYSIS_BACKEND_ALLOWED))
            raise ValueError(f"ANALYSIS_BACKEND must be one of: {allowed}")
        self.ANALYSIS_BACKEND = backend
        return self

    @property
    def mysql_url(self) -> str:
        """Build MySQL connection URL with URL-encoded password."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def traffic_proxy_lease_ttl_seconds(self) -> int:
        """Safe proxy-port lease TTL in seconds."""
        return max(60, min(int(self.TRAFFIC_PROXY_LEASE_TTL_SECONDS), 12 * 3600))

    @property
    def REDIS_PORT(self) -> int:  # noqa: N802 - keep backward-compatible settings contract
        """Back-compatible redis port field derived from broker URL."""
        parsed = urlparse(self.REDIS_BROKER_URL)
        return int(parsed.port or 6379)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache()
def cached_settings() -> Settings:
    """Get cached settings instance for tests."""
    return Settings()


settings = cached_settings()
