"""Configuration management using Pydantic Settings."""
from functools import lru_cache
from typing import Optional, List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # MySQL Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "apk_analysis"

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_CLUSTER_NODES: str = ""  # Comma-separated list of host:port

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

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    @property
    def mysql_url(self) -> str:
        """Build MySQL connection URL with URL-encoded password."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.MYSQL_PASSWORD)
        return f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def redis_cluster_nodes(self) -> List[str]:
        """Get Redis cluster nodes as list."""
        if self.REDIS_CLUSTER_NODES:
            return [node.strip() for node in self.REDIS_CLUSTER_NODES.split(",")]
        return []

    @property
    def android_emulators(self) -> List[str]:
        """Get all Android emulator addresses."""
        return [
            self.ANDROID_EMULATOR_1,
            self.ANDROID_EMULATOR_2,
            self.ANDROID_EMULATOR_3,
            self.ANDROID_EMULATOR_4,
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
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
