# APK 智能动态分析平台实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个高并发 APK 智能动态分析与网络监控平台，支持批量上传 APK、AI 驱动动态分析、流量捕获与白名单过滤、PDF 报告生成。

**Architecture:** 采用 FastAPI + Celery + MySQL + Redis + MinIO 的微服务架构。API 层处理请求，Celery 负责任务调度，各功能模块独立开发可并行实施。

**Tech Stack:** Python 3.11+, FastAPI, Celery, MySQL 8.0, Redis 7.0, MinIO, mitmproxy, Open-AutoGLM, WeasyPrint

---

## Phase 1: 项目基础设施（优先级: P0）

### Task 1.1: 项目初始化

**Files:**
- Create: `requirements.txt`
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: 创建项目目录结构**

```bash
mkdir -p api/routers api/schemas core workers modules/apk_analyzer modules/android_runner modules/traffic_monitor modules/ai_driver modules/report_generator models templates tests
```

Expected: 目录结构创建成功

**Step 2: 创建 requirements.txt**

```text
# Web Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Database
sqlalchemy==2.0.25
pymysql==1.1.0
alembic==1.13.1

# Task Queue
celery==5.3.6
redis==5.0.1

# Object Storage
minio==7.2.3

# APK Analysis
androguard==3.4.0a1

# Traffic Monitor
mitmproxy==10.1.6

# PDF Generation
weasyprint==60.2
jinja2==3.1.3

# Docker
docker==7.0.0

# HTTP Client
httpx==0.26.0
openai==1.10.0

# Utilities
python-multipart==0.0.6
python-dotenv==1.0.0
pyyaml==6.0.1
tenacity==8.2.3

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-cov==4.1.0
httpx==0.26.0
```

**Step 3: 创建 .env.example**

```bash
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=apk_analysis

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your_access_key
MINIO_SECRET_KEY=your_secret_key
MINIO_BUCKET=apk-analysis
MINIO_SECURE=false

# AI Model
AI_BASE_URL=http://localhost:8000/v1
AI_MODEL_NAME=autoglm-phone-9b
AI_API_KEY=EMPTY

# API
API_TOKEN=your_api_token
```

**Step 4: 创建 .gitignore**

```text
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local

# Logs
*.log
logs/

# Testing
.pytest_cache/
.coverage
htmlcov/

# OS
.DS_Store
Thumbs.db
```

**Step 5: Commit**

```bash
git init
git add .
git commit -m "feat: initialize project structure"
```

---

### Task 1.2: 配置管理模块

**Files:**
- Create: `core/__init__.py`
- Create: `core/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
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

    # Import after setting env vars
    from core.config import settings

    assert settings.MYSQL_HOST == "test-host"
    assert settings.MYSQL_PORT == 3307
    assert settings.MYSQL_USER == "test-user"


def test_config_has_defaults():
    """Test that config has sensible defaults."""
    from core.config import settings

    assert settings.MYSQL_PORT == 3306
    assert settings.REDIS_PORT == 6379
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core'"

**Step 3: Write minimal implementation**

Create `core/__init__.py`:

```python
"""Core module for APK Analysis Platform."""
```

Create `core/config.py`:

```python
"""Configuration management using Pydantic Settings."""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


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

    # MinIO Configuration
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "apk-analysis"
    MINIO_SECURE: bool = False

    # AI Model Configuration
    AI_BASE_URL: str = "http://localhost:8000/v1"
    AI_MODEL_NAME: str = "autoglm-phone-9b"
    AI_API_KEY: str = "EMPTY"
    AI_MAX_TOKENS: int = 3000
    AI_TEMPERATURE: float = 0.1

    # API Configuration
    API_TOKEN: str = ""
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Celery Configuration
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    @property
    def mysql_url(self) -> str:
        """Build MySQL connection URL."""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/ tests/test_config.py
git commit -m "feat: add configuration management module"
```

---

### Task 1.3: 数据库连接模块

**Files:**
- Create: `core/database.py`
- Create: `tests/test_database.py`

**Step 1: Write the failing test**

Create `tests/test_database.py`:

```python
"""Test database module."""
import pytest
from sqlalchemy import text


def test_database_engine_created():
    """Test that database engine is created."""
    from core.database import engine

    assert engine is not None
    assert str(engine.url).startswith("mysql")


def test_session_local_created():
    """Test that session factory is created."""
    from core.database import SessionLocal

    assert SessionLocal is not None


def test_get_db_generator():
    """Test that get_db yields a session."""
    from core.database import get_db

    gen = get_db()
    db = next(gen)
    assert db is not None

    # Cleanup
    try:
        next(gen)
    except StopIteration:
        pass
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_database.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core.database'"

**Step 3: Write minimal implementation**

Create `core/database.py`:

```python
"""Database connection and session management."""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core.config import settings

# Create engine
engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


def get_db() -> Generator:
    """
    Dependency function to get database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_database.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/database.py tests/test_database.py
git commit -m "feat: add database connection module"
```

---

### Task 1.4: MinIO 存储封装

**Files:**
- Create: `core/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write the failing test**

Create `tests/test_storage.py`:

```python
"""Test storage module."""
import pytest
from unittest.mock import Mock, patch


def test_storage_client_created():
    """Test that storage client is created."""
    from core.storage import storage_client

    assert storage_client is not None


def test_generate_apk_path():
    """Test APK path generation."""
    from core.storage import StorageManager

    path = StorageManager.generate_apk_path("task-123", "abc123")
    assert path == "apks/task-123/abc123.apk"


def test_generate_screenshot_path():
    """Test screenshot path generation."""
    from core.storage import StorageManager

    path = StorageManager.generate_screenshot_path("task-123", 1)
    assert path == "screenshots/task-123/step_001.png"


def test_generate_report_path():
    """Test report path generation."""
    from core.storage import StorageManager

    path = StorageManager.generate_report_path("task-123")
    assert path == "reports/task-123/report.pdf"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'core.storage'"

**Step 3: Write minimal implementation**

Create `core/storage.py`:

```python
"""MinIO object storage management."""
import io
from typing import Optional

from minio import Minio
from minio.error import S3Error

from core.config import settings


class StorageManager:
    """Manager for MinIO object storage operations."""

    def __init__(self):
        """Initialize storage client."""
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Ensure the bucket exists, create if not."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except S3Error as e:
            # Log error but don't fail initialization
            print(f"Warning: Could not ensure bucket exists: {e}")

    @staticmethod
    def generate_apk_path(task_id: str, md5: str) -> str:
        """Generate path for APK file storage."""
        return f"apks/{task_id}/{md5}.apk"

    @staticmethod
    def generate_screenshot_path(task_id: str, step: int) -> str:
        """Generate path for screenshot storage."""
        return f"screenshots/{task_id}/step_{step:03d}.png"

    @staticmethod
    def generate_report_path(task_id: str) -> str:
        """Generate path for report storage."""
        return f"reports/{task_id}/report.pdf"

    def upload_file(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        """
        Upload file to MinIO.

        Args:
            object_name: Path in bucket
            data: File content as bytes
            content_type: MIME type

        Returns:
            True if successful
        """
        try:
            self.client.put_object(
                self.bucket,
                object_name,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
            return True
        except S3Error as e:
            print(f"Error uploading file: {e}")
            return False

    def download_file(self, object_name: str) -> Optional[bytes]:
        """
        Download file from MinIO.

        Args:
            object_name: Path in bucket

        Returns:
            File content as bytes, or None if not found
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            return response.read()
        except S3Error:
            return None

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> Optional[str]:
        """
        Get presigned URL for file download.

        Args:
            object_name: Path in bucket
            expires: URL expiration in seconds

        Returns:
            Presigned URL, or None if not found
        """
        try:
            from datetime import timedelta
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=timedelta(seconds=expires),
            )
            return url
        except S3Error:
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        Delete file from MinIO.

        Args:
            object_name: Path in bucket

        Returns:
            True if successful
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except S3Error:
            return False


# Global storage client instance
storage_client = StorageManager()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/storage.py tests/test_storage.py
git commit -m "feat: add MinIO storage module"
```

---

## Phase 2: 数据模型（优先级: P0）

### Task 2.1: 任务模型

**Files:**
- Create: `models/__init__.py`
- Create: `models/task.py`
- Create: `tests/test_task_model.py`

**Step 1: Write the failing test**

Create `tests/test_task_model.py`:

```python
"""Test task model."""
import pytest
from datetime import datetime


def test_task_model_fields():
    """Test task model has required fields."""
    from models.task import Task, TaskStatus, TaskPriority

    # Check status enum
    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.QUEUED == "queued"
    assert TaskStatus.STATIC_ANALYZING == "static_analyzing"
    assert TaskStatus.DYNAMIC_ANALYZING == "dynamic_analyzing"
    assert TaskStatus.REPORT_GENERATING == "report_generating"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"

    # Check priority enum
    assert TaskPriority.URGENT == "urgent"
    assert TaskPriority.NORMAL == "normal"
    assert TaskPriority.BATCH == "batch"


def test_task_model_creation():
    """Test task model can be created."""
    from models.task import Task, TaskStatus, TaskPriority

    task = Task(
        id="test-task-id",
        apk_file_name="test.apk",
        apk_file_size=1024000,
        apk_md5="abc123",
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
    )

    assert task.id == "test-task-id"
    assert task.apk_file_name == "test.apk"
    assert task.status == TaskStatus.PENDING
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_model.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models'"

**Step 3: Write minimal implementation**

Create `models/__init__.py`:

```python
"""Data models for APK Analysis Platform."""
from models.task import Task, TaskStatus, TaskPriority
from models.whitelist import WhitelistRule, WhitelistCategory
from models.analysis_result import AnalysisResult

__all__ = [
    "Task",
    "TaskStatus",
    "TaskPriority",
    "WhitelistRule",
    "WhitelistCategory",
    "AnalysisResult",
]
```

Create `models/task.py`:

```python
"""Task model for analysis jobs."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String, Integer, BigInteger, Text, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.mysql import JSON

from core.database import Base


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    QUEUED = "queued"
    STATIC_ANALYZING = "static_analyzing"
    DYNAMIC_ANALYZING = "dynamic_analyzing"
    REPORT_GENERATING = "report_generating"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskPriority(str, Enum):
    """Task priority enumeration."""

    URGENT = "urgent"
    NORMAL = "normal"
    BATCH = "batch"


class Task(Base):
    """Task model for APK analysis jobs."""

    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # APK File Information
    apk_file_name = Column(String(255), nullable=False)
    apk_file_size = Column(BigInteger, nullable=False)
    apk_md5 = Column(String(32), nullable=False, index=True)
    apk_sha256 = Column(String(64), nullable=True)
    apk_storage_path = Column(String(500), nullable=True)

    # Task Status
    status = Column(
        SQLEnum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority = Column(
        SQLEnum(TaskPriority),
        default=TaskPriority.NORMAL,
        nullable=False,
    )

    # Error Information
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Analysis Results (stored as JSON)
    static_analysis_result = Column(JSON, nullable=True)
    dynamic_analysis_result = Column(JSON, nullable=True)

    # Report
    report_storage_path = Column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, status={self.status}, apk={self.apk_file_name})>"

    def to_dict(self) -> dict:
        """Convert task to dictionary."""
        return {
            "id": self.id,
            "apk_file_name": self.apk_file_name,
            "apk_file_size": self.apk_file_size,
            "apk_md5": self.apk_md5,
            "status": self.status.value if self.status else None,
            "priority": self.priority.value if self.priority else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "report_storage_path": self.report_storage_path,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add models/ tests/test_task_model.py
git commit -m "feat: add task model"
```

---

### Task 2.2: 白名单模型

**Files:**
- Create: `models/whitelist.py`
- Create: `tests/test_whitelist_model.py`

**Step 1: Write the failing test**

Create `tests/test_whitelist_model.py`:

```python
"""Test whitelist model."""


def test_whitelist_category_enum():
    """Test whitelist category enum."""
    from models.whitelist import WhitelistCategory

    assert WhitelistCategory.SYSTEM == "system"
    assert WhitelistCategory.CDN == "cdn"
    assert WhitelistCategory.ANALYTICS == "analytics"
    assert WhitelistCategory.ADS == "ads"
    assert WhitelistCategory.THIRD_PARTY == "third_party"
    assert WhitelistCategory.CUSTOM == "custom"


def test_whitelist_rule_creation():
    """Test whitelist rule model creation."""
    from models.whitelist import WhitelistRule, WhitelistCategory

    rule = WhitelistRule(
        domain="*.google.com",
        category=WhitelistCategory.SYSTEM,
        description="Google services",
        is_active=True,
    )

    assert rule.domain == "*.google.com"
    assert rule.category == WhitelistCategory.SYSTEM
    assert rule.is_active is True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_whitelist_model.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models.whitelist'"

**Step 3: Write minimal implementation**

Create `models/whitelist.py`:

```python
"""Whitelist model for network filtering."""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, Boolean, Enum as SQLEnum

from core.database import Base


class WhitelistCategory(str, Enum):
    """Whitelist category enumeration."""

    SYSTEM = "system"
    CDN = "cdn"
    ANALYTICS = "analytics"
    ADS = "ads"
    THIRD_PARTY = "third_party"
    CUSTOM = "custom"


class WhitelistRule(Base):
    """Whitelist rule model for network filtering."""

    __tablename__ = "network_whitelist"

    id = Column(String(36), primary_key=True)
    domain = Column(String(255), nullable=False, index=True, comment="Domain pattern (supports wildcard *)")
    ip_range = Column(String(50), nullable=True, comment="IP range in CIDR format")
    category = Column(
        SQLEnum(WhitelistCategory),
        nullable=False,
        index=True,
        comment="Rule category",
    )
    description = Column(String(500), nullable=True, comment="Rule description")
    is_active = Column(Boolean, default=True, nullable=False, index=True, comment="Is rule active")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<WhitelistRule(id={self.id}, domain={self.domain}, category={self.category})>"

    def to_dict(self) -> dict:
        """Convert rule to dictionary."""
        return {
            "id": self.id,
            "domain": self.domain,
            "ip_range": self.ip_range,
            "category": self.category.value if self.category else None,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_whitelist_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add models/whitelist.py tests/test_whitelist_model.py
git commit -m "feat: add whitelist model"
```

---

### Task 2.3: 分析结果模型

**Files:**
- Create: `models/analysis_result.py`
- Create: `tests/test_analysis_result_model.py`

**Step 1: Write the failing test**

Create `tests/test_analysis_result_model.py`:

```python
"""Test analysis result model."""


def test_permission_info():
    """Test permission info model."""
    from models.analysis_result import PermissionInfo

    perm = PermissionInfo(
        name="android.permission.INTERNET",
        protection_level="normal",
        description="Full network access",
        risk_level="low",
    )

    assert perm.name == "android.permission.INTERNET"
    assert perm.protection_level == "normal"
    assert perm.risk_level == "low"


def test_network_request():
    """Test network request model."""
    from models.analysis_result import NetworkRequest

    req = NetworkRequest(
        domain="example.com",
        ip="1.2.3.4",
        port=443,
        method="GET",
        is_https=True,
        is_whitelisted=False,
    )

    assert req.domain == "example.com"
    assert req.is_https is True
    assert req.is_whitelisted is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_analysis_result_model.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'models.analysis_result'"

**Step 3: Write minimal implementation**

Create `models/analysis_result.py`:

```python
"""Analysis result models for APK analysis."""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class RiskLevel(str, Enum):
    """Risk level enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ===== Static Analysis Models =====


class PermissionInfo(BaseModel):
    """Permission information model."""

    name: str
    protection_level: str = "normal"
    description: Optional[str] = None
    risk_level: str = "low"
    risk_reason: Optional[str] = None


class ComponentInfo(BaseModel):
    """Android component information model."""

    component_type: str  # activity, service, receiver, provider
    component_name: str
    is_exported: bool = False
    intent_filters: List[str] = []
    risk_level: str = "low"


class ApkBasicInfo(BaseModel):
    """APK basic information model."""

    package_name: str
    app_name: Optional[str] = None
    version_name: Optional[str] = None
    version_code: Optional[int] = None
    min_sdk: Optional[int] = None
    target_sdk: Optional[int] = None
    file_size: int = 0
    md5: str
    sha256: Optional[str] = None
    signature: Optional[str] = None
    is_debuggable: bool = False
    is_packed: bool = False
    packer_name: Optional[str] = None


class StaticAnalysisResult(BaseModel):
    """Static analysis result model."""

    basic_info: ApkBasicInfo
    permissions: List[PermissionInfo] = []
    components: List[ComponentInfo] = []
    native_libraries: List[str] = []
    suspicious_apis: List[str] = []
    analysis_time: datetime = datetime.utcnow()


# ===== Dynamic Analysis Models =====


class NetworkRequest(BaseModel):
    """Network request information model."""

    request_id: str
    url: str
    domain: str
    ip: Optional[str] = None
    port: int = 443
    method: str = "GET"
    is_https: bool = True
    request_time: datetime = datetime.utcnow()
    response_code: Optional[int] = None
    content_type: Optional[str] = None
    is_whitelisted: bool = False
    whitelist_category: Optional[str] = None
    risk_level: str = "low"
    risk_reason: Optional[str] = None


class SensitiveApiCall(BaseModel):
    """Sensitive API call information model."""

    api_name: str
    api_class: str
    call_count: int = 1
    first_call_time: datetime = datetime.utcnow()
    last_call_time: datetime = datetime.utcnow()
    risk_level: str = "medium"
    description: Optional[str] = None


class Screenshot(BaseModel):
    """Screenshot information model."""

    screenshot_id: str
    step_number: int
    operation_type: str  # tap, swipe, type, launch
    operation_detail: Optional[str] = None
    screenshot_path: str
    capture_time: datetime = datetime.utcnow()
    ai_description: Optional[str] = None


class DynamicAnalysisResult(BaseModel):
    """Dynamic analysis result model."""

    network_requests: List[NetworkRequest] = []
    sensitive_api_calls: List[SensitiveApiCall] = []
    screenshots: List[Screenshot] = []
    analysis_duration_seconds: int = 0
    analysis_time: datetime = datetime.utcnow()


# ===== Complete Analysis Result =====


class AnalysisResult(BaseModel):
    """Complete analysis result model."""

    task_id: str
    static_analysis: Optional[StaticAnalysisResult] = None
    dynamic_analysis: Optional[DynamicAnalysisResult] = None

    # Risk summary
    overall_risk_level: RiskLevel = RiskLevel.LOW
    risk_points: List[str] = []
    recommendations: List[str] = []

    analysis_time: datetime = datetime.utcnow()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_analysis_result_model.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add models/analysis_result.py tests/test_analysis_result_model.py
git commit -m "feat: add analysis result models"
```

---

## Phase 3: API Gateway（优先级: P0）

### Task 3.1: FastAPI 应用入口

**Files:**
- Create: `api/__init__.py`
- Create: `api/main.py`
- Create: `tests/test_api_main.py`

**Step 1: Write the failing test**

Create `tests/test_api_main.py`:

```python
"""Test API main module."""
from fastapi.testclient import TestClient


def test_api_health_check():
    """Test API health check endpoint."""
    from api.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_api_root():
    """Test API root endpoint."""
    from api.main import app

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "message" in response.json()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_main.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'api'"

**Step 3: Write minimal implementation**

Create `api/__init__.py`:

```python
"""API module for APK Analysis Platform."""
```

Create `api/main.py`:

```python
"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown: Cleanup if needed


# Create FastAPI application
app = FastAPI(
    title="APK Analysis Platform API",
    description="API for APK intelligent dynamic analysis and network monitoring",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "APK Analysis Platform API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Include routers (will be added in subsequent tasks)
# from api.routers import tasks, apk, whitelist
# app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
# app.include_router(apk.router, prefix="/api/v1", tags=["apk"])
# app.include_router(whitelist.router, prefix="/api/v1", tags=["whitelist"])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_main.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add api/ tests/test_api_main.py
git commit -m "feat: add FastAPI application entry point"
```

---

### Task 3.2: APK 上传接口

**Files:**
- Create: `api/schemas/__init__.py`
- Create: `api/schemas/apk.py`
- Create: `api/schemas/task.py`
- Create: `api/routers/__init__.py`
- Create: `api/routers/apk.py`
- Create: `tests/test_apk_router.py`

**Step 1: Write the failing test**

Create `tests/test_apk_router.py`:

```python
"""Test APK router."""
from fastapi.testclient import TestClient
import io


def test_upload_apk_success():
    """Test successful APK upload."""
    from api.main import app

    client = TestClient(app)

    # Create a fake APK file
    fake_apk = io.BytesIO(b"fake apk content")

    response = client.post(
        "/api/v1/apk/upload",
        files={"file": ("test.apk", fake_apk, "application/vnd.android.package-archive")},
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert "file_name" in data


def test_upload_invalid_file():
    """Test upload with invalid file type."""
    from api.main import app

    client = TestClient(app)

    # Create a non-APK file
    fake_file = io.BytesIO(b"not an apk")

    response = client.post(
        "/api/v1/apk/upload",
        files={"file": ("test.txt", fake_file, "text/plain")},
    )

    assert response.status_code == 400
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_apk_router.py -v`
Expected: FAIL with "AttributeError: 'APKUploadResponse' object has no attribute 'task_id'"

**Step 3: Write minimal implementation**

Create `api/schemas/__init__.py`:

```python
"""API schemas module."""
```

Create `api/schemas/apk.py`:

```python
"""APK schemas for API."""
from pydantic import BaseModel


class APKUploadResponse(BaseModel):
    """Response for APK upload."""

    task_id: str
    file_name: str
    file_size: int
    md5: str
    message: str = "APK uploaded successfully"
```

Create `api/schemas/task.py`:

```python
"""Task schemas for API."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskCreateRequest(BaseModel):
    """Request to create/start an analysis task."""

    task_id: str


class TaskResponse(BaseModel):
    """Response for task status."""

    id: str
    apk_file_name: str
    apk_file_size: int
    apk_md5: str
    status: str
    priority: str
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    report_url: Optional[str] = None


class TaskListResponse(BaseModel):
    """Response for task list."""

    total: int
    items: list
    page: int
    page_size: int
```

Create `api/routers/__init__.py`:

```python
"""API routers module."""
```

Create `api/routers/apk.py`:

```python
"""APK upload router."""
import hashlib
import uuid
from io import BytesIO

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlalchemy.orm import Session

from api.schemas.apk import APKUploadResponse
from core.config import settings
from core.database import get_db
from core.storage import StorageManager
from models.task import Task, TaskStatus, TaskPriority

router = APIRouter()


@router.post("/apk/upload", response_model=APKUploadResponse)
async def upload_apk(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload APK file for analysis.

    Args:
        file: APK file to upload
        db: Database session

    Returns:
        APKUploadResponse with task_id
    """
    # Validate file extension
    if not file.filename or not file.filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="File must be an APK file")

    # Read file content
    content = await file.read()

    # Calculate MD5
    md5_hash = hashlib.md5(content).hexdigest()

    # Generate task ID
    task_id = str(uuid.uuid4())

    # Upload to MinIO
    storage_path = StorageManager.generate_apk_path(task_id, md5_hash)
    from core.storage import storage_client
    storage_client.upload_file(storage_path, content, "application/vnd.android.package-archive")

    # Create task record
    task = Task(
        id=task_id,
        apk_file_name=file.filename,
        apk_file_size=len(content),
        apk_md5=md5_hash,
        apk_storage_path=storage_path,
        status=TaskStatus.PENDING,
        priority=TaskPriority.NORMAL,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return APKUploadResponse(
        task_id=task.id,
        file_name=file.filename,
        file_size=len(content),
        md5=md5_hash,
    )
```

**Step 4: Update main.py to include router**

Edit `api/main.py`, add at the end before the last comment:

```python
from api.routers import apk
app.include_router(apk.router, prefix="/api/v1", tags=["apk"])
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_apk_router.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add api/ tests/test_apk_router.py
git commit -m "feat: add APK upload endpoint"
```

---

### Task 3.3: 任务管理接口

**Files:**
- Create: `api/routers/tasks.py`
- Create: `tests/test_tasks_router.py`

**Step 1: Write the failing test**

Create `tests/test_tasks_router.py`:

```python
"""Test tasks router."""
from fastapi.testclient import TestClient


def test_get_task_not_found():
    """Test getting non-existent task."""
    from api.main import app

    client = TestClient(app)
    response = client.get("/api/v1/tasks/non-existent-id")

    assert response.status_code == 404


def test_list_tasks():
    """Test listing tasks."""
    from api.main import app

    client = TestClient(app)
    response = client.get("/api/v1/tasks")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tasks_router.py -v`
Expected: FAIL with "404 Not Found"

**Step 3: Write minimal implementation**

Create `api/routers/tasks.py`:

```python
"""Task management router."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.task import TaskCreateRequest, TaskResponse, TaskListResponse
from core.database import get_db
from models.task import Task, TaskStatus

router = APIRouter()


@router.post("/tasks", response_model=TaskResponse)
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Start analysis for an uploaded APK.

    Args:
        request: Task creation request with task_id
        db: Database session

    Returns:
        TaskResponse with task details
    """
    task = db.query(Task).filter(Task.id == request.task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Task already started with status: {task.status}")

    # Update task status and queue it
    task.status = TaskStatus.QUEUED
    db.commit()
    db.refresh(task)

    # TODO: Queue task in Celery (will be implemented in Phase 4)

    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        status=task.status.value,
        priority=task.priority.value,
        error_message=task.error_message,
        retry_count=task.retry_count,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
):
    """
    Get task status and details.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        TaskResponse with task details
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    report_url = None
    if task.report_storage_path:
        from core.storage import storage_client
        report_url = storage_client.get_presigned_url(task.report_storage_path)

    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        status=task.status.value,
        priority=task.priority.value,
        error_message=task.error_message,
        retry_count=task.retry_count,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        report_url=report_url,
    )


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: str,
    db: Session = Depends(get_db),
):
    """
    Retry a failed task.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        TaskResponse with updated task details
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed tasks can be retried")

    # Reset task status
    task.status = TaskStatus.PENDING
    task.error_message = None
    task.error_stack = None
    task.retry_count += 1
    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=task.id,
        apk_file_name=task.apk_file_name,
        apk_file_size=task.apk_file_size,
        apk_md5=task.apk_md5,
        status=task.status.value,
        priority=task.priority.value,
        error_message=task.error_message,
        retry_count=task.retry_count,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
    )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List tasks with pagination and filtering.

    Args:
        page: Page number
        page_size: Items per page
        status: Filter by status
        db: Database session

    Returns:
        TaskListResponse with paginated tasks
    """
    query = db.query(Task)

    if status:
        try:
            status_enum = TaskStatus(status)
            query = query.filter(Task.status == status_enum)
        except ValueError:
            pass

    total = query.count()
    items = query.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return TaskListResponse(
        total=total,
        items=[TaskResponse(
            id=task.id,
            apk_file_name=task.apk_file_name,
            apk_file_size=task.apk_file_size,
            apk_md5=task.apk_md5,
            status=task.status.value,
            priority=task.priority.value,
            error_message=task.error_message,
            retry_count=task.retry_count,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        ) for task in items],
        page=page,
        page_size=page_size,
    )


@router.get("/tasks/{task_id}/report")
async def download_report(
    task_id: str,
    db: Session = Depends(get_db),
):
    """
    Download PDF report for completed task.

    Args:
        task_id: Task ID
        db: Database session

    Returns:
        PDF file download
    """
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task not completed yet")

    if not task.report_storage_path:
        raise HTTPException(status_code=404, detail="Report not found")

    from fastapi.responses import StreamingResponse
    from core.storage import storage_client
    import io

    report_content = storage_client.download_file(task.report_storage_path)
    if not report_content:
        raise HTTPException(status_code=404, detail="Report file not found")

    return StreamingResponse(
        io.BytesIO(report_content),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=report_{task_id}.pdf"
        },
    )
```

**Step 4: Update main.py to include tasks router**

Edit `api/main.py`, update the router imports:

```python
from api.routers import apk, tasks
app.include_router(apk.router, prefix="/api/v1", tags=["apk"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_tasks_router.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add api/routers/tasks.py tests/test_tasks_router.py
git commit -m "feat: add task management endpoints"
```

---

### Task 3.4: 白名单管理接口

**Files:**
- Create: `api/schemas/whitelist.py`
- Create: `api/routers/whitelist.py`
- Create: `tests/test_whitelist_router.py`

**Step 1: Write the failing test**

Create `tests/test_whitelist_router.py`:

```python
"""Test whitelist router."""
from fastapi.testclient import TestClient


def test_list_whitelist():
    """Test listing whitelist rules."""
    from api.main import app

    client = TestClient(app)
    response = client.get("/api/v1/whitelist")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data


def test_add_whitelist_rule():
    """Test adding a whitelist rule."""
    from api.main import app

    client = TestClient(app)

    rule_data = {
        "domain": "*.test.com",
        "category": "custom",
        "description": "Test rule",
    }

    response = client.post("/api/v1/whitelist", json=rule_data)

    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "*.test.com"
    assert data["category"] == "custom"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_whitelist_router.py -v`
Expected: FAIL with "404 Not Found"

**Step 3: Write minimal implementation**

Create `api/schemas/whitelist.py`:

```python
"""Whitelist schemas for API."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from models.whitelist import WhitelistCategory


class WhitelistCreateRequest(BaseModel):
    """Request to create a whitelist rule."""

    domain: str
    ip_range: Optional[str] = None
    category: WhitelistCategory
    description: Optional[str] = None
    is_active: bool = True


class WhitelistUpdateRequest(BaseModel):
    """Request to update a whitelist rule."""

    domain: Optional[str] = None
    ip_range: Optional[str] = None
    category: Optional[WhitelistCategory] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class WhitelistResponse(BaseModel):
    """Response for a whitelist rule."""

    id: str
    domain: str
    ip_range: Optional[str] = None
    category: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WhitelistListResponse(BaseModel):
    """Response for whitelist list."""

    total: int
    items: list
```

Create `api/routers/whitelist.py`:

```python
"""Whitelist management router."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.schemas.whitelist import (
    WhitelistCreateRequest,
    WhitelistUpdateRequest,
    WhitelistResponse,
    WhitelistListResponse,
)
from core.database import get_db
from models.whitelist import WhitelistRule, WhitelistCategory

router = APIRouter()


@router.get("/whitelist", response_model=WhitelistListResponse)
async def list_whitelist(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    category: str = None,
    is_active: bool = None,
    db: Session = Depends(get_db),
):
    """
    List whitelist rules with pagination and filtering.

    Args:
        page: Page number
        page_size: Items per page
        category: Filter by category
        is_active: Filter by active status
        db: Database session

    Returns:
        WhitelistListResponse with paginated rules
    """
    query = db.query(WhitelistRule)

    if category:
        try:
            category_enum = WhitelistCategory(category)
            query = query.filter(WhitelistRule.category == category_enum)
        except ValueError:
            pass

    if is_active is not None:
        query = query.filter(WhitelistRule.is_active == is_active)

    total = query.count()
    items = query.order_by(WhitelistRule.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return WhitelistListResponse(
        total=total,
        items=[WhitelistResponse(**rule.to_dict()) for rule in items],
    )


@router.post("/whitelist", response_model=WhitelistResponse)
async def add_whitelist_rule(
    request: WhitelistCreateRequest,
    db: Session = Depends(get_db),
):
    """
    Add a new whitelist rule.

    Args:
        request: Whitelist rule data
        db: Database session

    Returns:
        WhitelistResponse with created rule
    """
    rule = WhitelistRule(
        id=str(uuid.uuid4()),
        domain=request.domain,
        ip_range=request.ip_range,
        category=request.category,
        description=request.description,
        is_active=request.is_active,
    )

    db.add(rule)
    db.commit()
    db.refresh(rule)

    return WhitelistResponse(**rule.to_dict())


@router.put("/whitelist/{rule_id}", response_model=WhitelistResponse)
async def update_whitelist_rule(
    rule_id: str,
    request: WhitelistUpdateRequest,
    db: Session = Depends(get_db),
):
    """
    Update an existing whitelist rule.

    Args:
        rule_id: Rule ID
        request: Updated whitelist rule data
        db: Database session

    Returns:
        WhitelistResponse with updated rule
    """
    rule = db.query(WhitelistRule).filter(WhitelistRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = request.model_dump(exclude_unset=True)

    # Handle category conversion
    if "category" in update_data and isinstance(update_data["category"], WhitelistCategory):
        update_data["category"] = update_data["category"]

    for key, value in update_data.items():
        setattr(rule, key, value)

    db.commit()
    db.refresh(rule)

    return WhitelistResponse(**rule.to_dict())


@router.delete("/whitelist/{rule_id}")
async def delete_whitelist_rule(
    rule_id: str,
    db: Session = Depends(get_db),
):
    """
    Delete a whitelist rule.

    Args:
        rule_id: Rule ID
        db: Database session

    Returns:
        Success message
    """
    rule = db.query(WhitelistRule).filter(WhitelistRule.id == rule_id).first()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    db.delete(rule)
    db.commit()

    return {"message": "Rule deleted successfully"}
```

**Step 4: Update main.py to include whitelist router**

Edit `api/main.py`, update the router imports:

```python
from api.routers import apk, tasks, whitelist
app.include_router(apk.router, prefix="/api/v1", tags=["apk"])
app.include_router(tasks.router, prefix="/api/v1", tags=["tasks"])
app.include_router(whitelist.router, prefix="/api/v1", tags=["whitelist"])
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_whitelist_router.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add api/ tests/test_whitelist_router.py
git commit -m "feat: add whitelist management endpoints"
```

---

## Phase 4: Task Scheduler（优先级: P0）

### Task 4.1: Celery 应用配置

**Files:**
- Create: `workers/__init__.py`
- Create: `workers/celery_app.py`
- Create: `tests/test_celery_app.py`

**Step 1: Write the failing test**

Create `tests/test_celery_app.py`:

```python
"""Test Celery app configuration."""


def test_celery_app_created():
    """Test that Celery app is created."""
    from workers.celery_app import celery_app

    assert celery_app is not None
    assert celery_app.main == "workers"


def test_celery_config():
    """Test Celery configuration."""
    from workers.celery_app import celery_app

    assert "broker_url" in celery_app.conf
    assert "result_backend" in celery_app.conf
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_celery_app.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'workers'"

**Step 3: Write minimal implementation**

Create `workers/__init__.py`:

```python
"""Celery workers module."""
```

Create `workers/celery_app.py`:

```python
"""Celery application configuration."""
from celery import Celery

from core.config import settings

# Create Celery app
celery_app = Celery(
    "workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=3600,  # 1 hour timeout
    task_soft_time_limit=3300,  # 55 minutes soft timeout
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    result_expires=86400,  # 24 hours
    # Task routing
    task_routes={
        "workers.static_analyzer.*": {"queue": "static"},
        "workers.dynamic_analyzer.*": {"queue": "dynamic"},
        "workers.report_generator.*": {"queue": "report"},
    },
    # Task default queue
    task_default_queue="default",
)

# Autodiscover tasks from modules
celery_app.autodiscover_tasks(["workers"])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_celery_app.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add workers/ tests/test_celery_app.py
git commit -m "feat: add Celery application configuration"
```

---

### Task 4.2: 静态分析任务

**Files:**
- Create: `workers/static_analyzer.py`
- Create: `modules/__init__.py`
- Create: `modules/apk_analyzer/__init__.py`
- Create: `modules/apk_analyzer/analyzer.py`
- Create: `tests/test_static_analyzer.py`

**Step 1: Write the failing test**

Create `tests/test_static_analyzer.py`:

```python
"""Test static analyzer."""
import pytest


def test_static_analysis_task_registered():
    """Test that static analysis task is registered."""
    from workers.celery_app import celery_app

    assert "workers.static_analyzer.run_static_analysis" in celery_app.tasks


def test_apk_analyzer_extract_package_name():
    """Test APK analyzer can extract package name."""
    from modules.apk_analyzer.analyzer import ApkAnalyzer

    # This is a placeholder test - real test needs actual APK
    analyzer = ApkAnalyzer()
    assert analyzer is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_static_analyzer.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

Create `modules/__init__.py`:

```python
"""Modules for APK Analysis Platform."""
```

Create `modules/apk_analyzer/__init__.py`:

```python
"""APK Analyzer module."""
from modules.apk_analyzer.analyzer import ApkAnalyzer

__all__ = ["ApkAnalyzer"]
```

Create `modules/apk_analyzer/analyzer.py`:

```python
"""APK static analyzer using androguard."""
import hashlib
from typing import Dict, List, Any, Optional
import logging

from androguard.core.bytecodes.apk import APK

from models.analysis_result import (
    ApkBasicInfo,
    PermissionInfo,
    ComponentInfo,
    StaticAnalysisResult,
)

logger = logging.getLogger(__name__)


# Dangerous permissions mapping
DANGEROUS_PERMISSIONS = {
    "android.permission.READ_CONTACTS": ("high", "读取联系人"),
    "android.permission.WRITE_CONTACTS": ("high", "写入联系人"),
    "android.permission.READ_SMS": ("high", "读取短信"),
    "android.permission.SEND_SMS": ("high", "发送短信"),
    "android.permission.RECEIVE_SMS": ("high", "接收短信"),
    "android.permission.READ_CALL_LOG": ("high", "读取通话记录"),
    "android.permission.WRITE_CALL_LOG": ("high", "写入通话记录"),
    "android.permission.PROCESS_OUTGOING_CALLS": ("high", "监听拨出电话"),
    "android.permission.READ_PHONE_STATE": ("medium", "读取设备状态"),
    "android.permission.ACCESS_FINE_LOCATION": ("high", "精确定位"),
    "android.permission.ACCESS_COARSE_LOCATION": ("medium", "粗略定位"),
    "android.permission.CAMERA": ("medium", "使用相机"),
    "android.permission.RECORD_AUDIO": ("high", "录音"),
    "android.permission.READ_EXTERNAL_STORAGE": ("medium", "读取存储"),
    "android.permission.WRITE_EXTERNAL_STORAGE": ("medium", "写入存储"),
}


class ApkAnalyzer:
    """APK static analyzer class."""

    def __init__(self):
        """Initialize APK analyzer."""
        self.apk: Optional[APK] = None

    def load_apk(self, apk_path: str) -> bool:
        """
        Load APK file for analysis.

        Args:
            apk_path: Path to APK file

        Returns:
            True if loaded successfully
        """
        try:
            self.apk = APK(apk_path)
            return True
        except Exception as e:
            logger.error(f"Failed to load APK: {e}")
            return False

    def load_apk_from_bytes(self, apk_content: bytes) -> bool:
        """
        Load APK from bytes.

        Args:
            apk_content: APK file content as bytes

        Returns:
            True if loaded successfully
        """
        try:
            self.apk = APK(apk_content, raw=True)
            return True
        except Exception as e:
            logger.error(f"Failed to load APK from bytes: {e}")
            return False

    def extract_basic_info(self, file_size: int = 0, md5: str = "", sha256: str = "") -> ApkBasicInfo:
        """
        Extract basic information from APK.

        Args:
            file_size: File size in bytes
            md5: MD5 hash
            sha256: SHA256 hash

        Returns:
            ApkBasicInfo object
        """
        if not self.apk:
            raise ValueError("APK not loaded")

        return ApkBasicInfo(
            package_name=self.apk.get_package() or "",
            app_name=self.apk.get_app_name() or "",
            version_name=self.apk.get_androidversion_name() or "",
            version_code=self.apk.get_androidversion_code(),
            min_sdk=self.apk.get_min_sdk_version(),
            target_sdk=self.apk.get_target_sdk_version(),
            file_size=file_size,
            md5=md5,
            sha256=sha256,
            signature=self._get_signature_info(),
            is_debuggable=self.apk.is_debuggable(),
            is_packed=False,  # TODO: Add packer detection
            packer_name=None,
        )

    def extract_permissions(self) -> List[PermissionInfo]:
        """
        Extract permissions from APK.

        Returns:
            List of PermissionInfo objects
        """
        if not self.apk:
            raise ValueError("APK not loaded")

        permissions = []
        for perm in self.apk.get_permissions():
            perm_name = perm.split(".")[-1] if "." in perm else perm
            protection_level = "unknown"

            # Determine protection level
            if perm in DANGEROUS_PERMISSIONS:
                risk_level, risk_reason = DANGEROUS_PERMISSIONS[perm]
                protection_level = "dangerous" if risk_level in ("high", "critical") else "normal"
            else:
                risk_level = "low"
                risk_reason = None

            permissions.append(PermissionInfo(
                name=perm,
                protection_level=protection_level,
                description=risk_reason,
                risk_level=risk_level,
                risk_reason=risk_reason,
            ))

        return permissions

    def extract_components(self) -> List[ComponentInfo]:
        """
        Extract Android components from APK.

        Returns:
            List of ComponentInfo objects
        """
        if not self.apk:
            raise ValueError("APK not loaded")

        components = []

        # Activities
        for activity in self.apk.get_activities():
            is_exported = self._is_component_exported(activity, "activity")
            components.append(ComponentInfo(
                component_type="activity",
                component_name=activity,
                is_exported=is_exported,
                intent_filters=[],  # TODO: Extract intent filters
                risk_level="high" if is_exported else "low",
            ))

        # Services
        for service in self.apk.get_services():
            is_exported = self._is_component_exported(service, "service")
            components.append(ComponentInfo(
                component_type="service",
                component_name=service,
                is_exported=is_exported,
                intent_filters=[],
                risk_level="high" if is_exported else "low",
            ))

        # Receivers
        for receiver in self.apk.get_receivers():
            is_exported = self._is_component_exported(receiver, "receiver")
            components.append(ComponentInfo(
                component_type="receiver",
                component_name=receiver,
                is_exported=is_exported,
                intent_filters=[],
                risk_level="high" if is_exported else "low",
            ))

        # Providers
        for provider in self.apk.get_providers():
            is_exported = self._is_component_exported(provider, "provider")
            components.append(ComponentInfo(
                component_type="provider",
                component_name=provider,
                is_exported=is_exported,
                intent_filters=[],
                risk_level="high" if is_exported else "low",
            ))

        return components

    def analyze(self, apk_content: bytes, md5: str, sha256: str = "") -> StaticAnalysisResult:
        """
        Perform full static analysis.

        Args:
            apk_content: APK file content
            md5: MD5 hash
            sha256: SHA256 hash

        Returns:
            StaticAnalysisResult object
        """
        if not self.load_apk_from_bytes(apk_content):
            raise ValueError("Failed to load APK")

        basic_info = self.extract_basic_info(
            file_size=len(apk_content),
            md5=md5,
            sha256=sha256,
        )

        permissions = self.extract_permissions()
        components = self.extract_components()

        return StaticAnalysisResult(
            basic_info=basic_info,
            permissions=permissions,
            components=components,
            native_libraries=self._get_native_libraries(),
            suspicious_apis=[],  # TODO: Add suspicious API detection
        )

    def _get_signature_info(self) -> Optional[str]:
        """Get APK signature information."""
        try:
            if self.apk:
                certs = self.apk.get_certificates()
                if certs:
                    cert = certs[0]
                    return f"CN={cert.issuer}"
        except Exception:
            pass
        return None

    def _is_component_exported(self, component_name: str, component_type: str) -> bool:
        """Check if component is exported."""
        try:
            if self.apk:
                # Try to get the manifest element
                manifest = self.apk.get_android_manifest_xml()
                xpath = f".//{component_type}[@android:name='{component_name}']"
                elements = manifest.findall(xpath, {"android": "http://schemas.android.com/apk/res/android"})
                if elements:
                    elem = elements[0]
                    exported = elem.get("{http://schemas.android.com/apk/res/android}exported")
                    if exported is not None:
                        return exported.lower() == "true"
                    # If no intent-filters, default exported is false
                    # If has intent-filters, default exported is true
                    intent_filters = elem.findall(".//intent-filter")
                    return len(intent_filters) > 0
        except Exception:
            pass
        return False

    def _get_native_libraries(self) -> List[str]:
        """Get list of native libraries."""
        try:
            if self.apk:
                return list(self.apk.get_libraries())
        except Exception:
            pass
        return []
```

Create `workers/static_analyzer.py`:

```python
"""Celery task for static analysis."""
import logging
from datetime import datetime

from workers.celery_app import celery_app
from core.database import SessionLocal
from core.storage import storage_client
from models.task import Task, TaskStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_static_analysis(self, task_id: str):
    """
    Run static analysis for an APK.

    Args:
        task_id: Task ID to analyze
    """
    db = SessionLocal()

    try:
        # Get task
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Update status
        task.status = TaskStatus.STATIC_ANALYZING
        task.started_at = datetime.utcnow()
        db.commit()

        logger.info(f"Starting static analysis for task {task_id}")

        # Download APK from MinIO
        apk_content = storage_client.download_file(task.apk_storage_path)
        if not apk_content:
            raise ValueError(f"Failed to download APK: {task.apk_storage_path}")

        # Run analysis
        from modules.apk_analyzer.analyzer import ApkAnalyzer
        import hashlib

        sha256 = hashlib.sha256(apk_content).hexdigest()

        analyzer = ApkAnalyzer()
        result = analyzer.analyze(apk_content, task.apk_md5, sha256)

        # Update task with results
        task.apk_sha256 = sha256
        task.static_analysis_result = result.model_dump()

        logger.info(f"Static analysis completed for task {task_id}")

    except Exception as e:
        logger.error(f"Static analysis failed for task {task_id}: {e}")
        if db:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                db.commit()
        raise self.retry(exc=e)

    finally:
        db.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_static_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add modules/apk_analyzer/ workers/static_analyzer.py tests/test_static_analyzer.py
git commit -m "feat: add APK static analyzer and Celery task"
```

---

## Phase 5: 后续模块（优先级: P1）

由于篇幅限制，后续模块的实施计划简述如下：

### Task 5.1: Docker-Android Runner（modules/android_runner/）
- 容器生命周期管理
- ADB 连接封装
- APK 安装/卸载
- 截图捕获

### Task 5.2: Traffic Monitor（modules/traffic_monitor/）
- mitmproxy 集成
- SSL 证书安装
- 流量实时解析
- 白名单过滤逻辑

### Task 5.3: AI Driver（modules/ai_driver/）
- Open-AutoGLM 客户端封装
- 截图分析与决策
- 操作指令生成

### Task 5.4: Report Generator（modules/report_generator/）
- Jinja2 HTML 模板
- WeasyPrint PDF 生成
- 报告存储

### Task 5.5: Dynamic Analyzer Task（workers/dynamic_analyzer.py）
- 整合 Android Runner + Traffic Monitor + AI Driver
- 动态分析流程编排

### Task 5.6: Report Generator Task（workers/report_generator.py）
- 生成 PDF 报告
- 更新任务状态

---

## 执行顺序建议

```
Phase 1 (基础设施)
    └── Task 1.1 → Task 1.2 → Task 1.3 → Task 1.4 (可并行)

Phase 2 (数据模型)
    └── Task 2.1 → Task 2.2 → Task 2.3 (可并行)

Phase 3 (API Gateway)
    └── Task 3.1 → Task 3.2 → Task 3.3 → Task 3.4 (部分可并行)

Phase 4 (Task Scheduler)
    └── Task 4.1 → Task 4.2

Phase 5 (功能模块)
    └── Task 5.1, 5.2, 5.3 (可并行) → Task 5.4 → Task 5.5 → Task 5.6
```

---

## 启动命令

### 开发环境启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 MySQL, Redis, MinIO (使用 docker-compose)
docker-compose up -d

# 3. 运行数据库迁移
alembic upgrade head

# 4. 启动 API 服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 5. 启动 Celery Worker
celery -A workers.celery_app worker -l info -Q default,static,dynamic,report
```

### 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行覆盖率测试
pytest tests/ --cov=. --cov-report=html
```

