"""Database connection and session management."""
import ssl
from typing import Generator

from sqlalchemy import create_engine, text
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
