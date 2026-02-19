"""Database connection and session management."""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core.config import settings

# Pool configuration constants
POOL_SIZE = 20  # Base connections for typical concurrent load
MAX_OVERFLOW = 10  # Additional connections for burst traffic (50% of base)
POOL_RECYCLE_SECONDS = 3600  # Recycle connections after 1 hour to prevent MySQL timeout

# Create engine
engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_recycle=POOL_RECYCLE_SECONDS,
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

    Note:
        Database errors during session usage propagate to the caller.
        The session is always closed via finally block, even on error.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
