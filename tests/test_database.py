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
