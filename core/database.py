"""Database connection and session management."""
import json
import ssl
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core.config import settings

# Pool configuration constants
POOL_SIZE = 20  # Base connections for typical concurrent load
MAX_OVERFLOW = 10  # Additional connections for burst traffic (50% of base)
POOL_RECYCLE_SECONDS = 3600  # Recycle connections after 1 hour to prevent MySQL timeout

# Create SSL context for MySQL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create engine with SSL
engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE_SECONDS,
    echo=False,
    connect_args={"ssl": ssl_context}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()


SCHEMA_LOCK_NAME = "app_analysis_schema_init"
SCHEMA_LOCK_TIMEOUT_SECONDS = 120


def _ensure_tasks_table_columns(connection) -> None:
    """Add lightweight task columns required by the current status model."""
    inspector = inspect(connection)
    try:
        columns = {column["name"] for column in inspector.get_columns("tasks")}
    except Exception:
        return

    ddl_statements = []
    if "failure_reason" not in columns:
        ddl_statements.append("ALTER TABLE tasks ADD COLUMN failure_reason TEXT NULL")
    if "last_success_stage" not in columns:
        ddl_statements.append("ALTER TABLE tasks ADD COLUMN last_success_stage VARCHAR(32) NULL")

    for ddl in ddl_statements:
        connection.execute(text(ddl))


def _seed_android_permission_catalog(connection) -> None:
    """Seed Android permission catalog from the checked-in JSON dataset."""
    from models.analysis_tables import AndroidPermissionCatalogTable

    inspector = inspect(connection)
    try:
        if "android_permission_catalog" not in inspector.get_table_names():
            return
    except Exception:
        return

    count = connection.execute(
        text("SELECT COUNT(*) FROM android_permission_catalog")
    ).scalar()
    if count and int(count) > 0:
        return

    catalog_path = (
        Path(__file__).resolve().parents[1] / "data" / "android_permission_catalog.json"
    )
    if not catalog_path.exists():
        return

    try:
        rows = json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception:
        return

    if not isinstance(rows, list) or not rows:
        return

    payload = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        payload.append(
            {
                "code": code,
                "description_en": row.get("description_en"),
                "description_zh": row.get("description_zh"),
                "source_url": row.get("source_url"),
            }
        )

    if payload:
        connection.execute(AndroidPermissionCatalogTable.__table__.insert(), payload)


def ensure_schema_ready() -> None:
    """Create tables under a MySQL advisory lock.

    This prevents multiple uvicorn workers from racing inside
    ``Base.metadata.create_all(...)`` during startup.
    """

    lock_sql = text("SELECT GET_LOCK(:name, :timeout)")
    unlock_sql = text("SELECT RELEASE_LOCK(:name)")

    with engine.connect() as connection:
        lock_result = connection.execute(
            lock_sql,
            {"name": SCHEMA_LOCK_NAME, "timeout": SCHEMA_LOCK_TIMEOUT_SECONDS},
        ).scalar()
        if lock_result != 1:
            raise RuntimeError("Could not acquire schema initialization lock")

        try:
            Base.metadata.create_all(bind=connection)
            _ensure_tasks_table_columns(connection)
            _seed_android_permission_catalog(connection)
            connection.commit()
        finally:
            connection.execute(unlock_sql, {"name": SCHEMA_LOCK_NAME})
            connection.commit()


def get_db() -> Generator:
    """
    Dependency function to get database session.

    Yields:
        Database session

    Note:
        Database errors during session usage propagate to the caller.
        The session is always closed via finally block, even on error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
