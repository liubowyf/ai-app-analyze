"""Configuration management using Pydantic Settings."""
import json
from functools import lru_cache
from urllib.parse import quote, urlparse, urlunsplit
from typing import Any, ClassVar

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
    REDROID_HOST_AGENT_BASE_URL: str = ""
    REDROID_HOST_AGENT_TOKEN: str = ""
    REDROID_HOST_AGENT_TIMEOUT_SECONDS: int = 15
    REDROID_CONTAINER_NAME: str = "redroid-1"
    REDROID_CAPTURE_SECONDS: int = 120
    REDROID_SLOTS_JSON: str = ""
    REDROID_LEASE_TTL_SECONDS: int = 1800
    REDROID_LEASE_ACQUIRE_TIMEOUT_SECONDS: int = 300
    REDROID_LEASE_POLL_INTERVAL_SECONDS: float = 2.0
    ALIYUN_IP_GEO_ENABLED: bool = False
    ALIYUN_IP_GEO_BASE_URL: str = "https://dm-81.data.aliyun.com"
    ALIYUN_IP_GEO_APPCODE: str = ""
    ALIYUN_IP_GEO_APPKEY: str = ""
    ALIYUN_IP_GEO_APPSECRET: str = ""
    ALIYUN_IP_GEO_TIMEOUT_SECONDS: int = 8
    ALIYUN_IP_GEO_MAX_CONCURRENCY: int = 10
    ALIYUN_IP_GEO_ENABLED: bool = False
    ALIYUN_IP_GEO_BASE_URL: str = "http://10.16.135.135:9093/openapi/ip/location"
    ALIYUN_IP_GEO_APPCODE: str = ""
    ALIYUN_IP_GEO_APPKEY: str = ""
    ALIYUN_IP_GEO_APPSECRET: str = ""
    ALIYUN_IP_GEO_TIMEOUT_SECONDS: int = 10
    ALIYUN_IP_GEO_MAX_CONCURRENCY: int = 10

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

    @model_validator(mode="after")
    def validate_ip_geo_limits(self) -> "Settings":
        self.ALIYUN_IP_GEO_MAX_CONCURRENCY = max(1, min(int(self.ALIYUN_IP_GEO_MAX_CONCURRENCY), 30))
        self.ALIYUN_IP_GEO_TIMEOUT_SECONDS = max(1, int(self.ALIYUN_IP_GEO_TIMEOUT_SECONDS))
        return self

    @model_validator(mode="after")
    def clamp_ip_geo_concurrency(self) -> "Settings":
        """Keep third-party geo lookups within provider concurrency limits."""
        self.ALIYUN_IP_GEO_MAX_CONCURRENCY = max(
            1,
            min(int(self.ALIYUN_IP_GEO_MAX_CONCURRENCY or 1), 30),
        )
        self.ALIYUN_IP_GEO_TIMEOUT_SECONDS = max(1, int(self.ALIYUN_IP_GEO_TIMEOUT_SECONDS or 1))
        return self

    @property
    def redroid_slots(self) -> list[dict[str, str]]:
        """Return configured redroid execution slots."""
        raw = (self.REDROID_SLOTS_JSON or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("REDROID_SLOTS_JSON must be valid JSON") from exc
            if not isinstance(parsed, list) or not parsed:
                raise ValueError("REDROID_SLOTS_JSON must be a non-empty list")

            slots: list[dict[str, str]] = []
            for index, item in enumerate(parsed, start=1):
                if not isinstance(item, dict):
                    raise ValueError("Each REDROID_SLOTS_JSON item must be an object")
                adb_serial = str(item.get("adb_serial") or "").strip()
                container_name = str(item.get("container_name") or "").strip()
                name = str(item.get("name") or f"redroid-{index}").strip()
                if not adb_serial or not container_name:
                    raise ValueError("Each REDROID_SLOTS_JSON item requires adb_serial and container_name")
                slots.append(
                    {
                        "name": name,
                        "adb_serial": adb_serial,
                        "container_name": container_name,
                    }
                )
            return slots

        return [
            {
                "name": self.REDROID_CONTAINER_NAME,
                "adb_serial": self.REDROID_ADB_SERIAL,
                "container_name": self.REDROID_CONTAINER_NAME,
            }
        ]

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
