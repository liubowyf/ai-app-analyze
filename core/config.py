"""Configuration management using Pydantic Settings."""
from functools import lru_cache
from urllib.parse import urlparse
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    # Android Emulators Configuration
    ANDROID_EMULATOR_1: str = "10.16.148.66:5555"
    ANDROID_EMULATOR_2: str = "10.16.148.66:5556"
    ANDROID_EMULATOR_3: str = "10.16.148.66:5557"
    ANDROID_EMULATOR_4: str = "10.16.148.66:5558"

    # API Configuration
    API_TOKEN: str = ""
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Task Queue Configuration (Dramatiq + Redis)
    TASK_BACKEND: str = "dramatiq"
    REDIS_BROKER_URL: str = "redis://localhost:6379/0"
    TASK_ACTOR_LOCK_TTL_SECONDS: int = 300
    TASK_ACTOR_RETRY_BACKOFF_SECONDS: str = "10,30,60"
    EMULATOR_LEASE_TTL_SECONDS: int = 3900
    TRAFFIC_PROXY_PORT_START: int = 18080
    TRAFFIC_PROXY_PORT_END: int = 18129
    TRAFFIC_PROXY_LEASE_TTL_SECONDS: int = 3900

    @property
    def mysql_url(self) -> str:
        """Build MySQL connection URL with URL-encoded password."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def android_emulators(self) -> List[str]:
        """Get all Android emulator addresses."""
        return [
            self.ANDROID_EMULATOR_1,
            self.ANDROID_EMULATOR_2,
            self.ANDROID_EMULATOR_3,
            self.ANDROID_EMULATOR_4,
        ]

    @property
    def emulator_lease_ttl_seconds(self) -> int:
        """Safe emulator lease TTL in seconds."""
        return max(60, min(int(self.EMULATOR_LEASE_TTL_SECONDS), 12 * 3600))

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
