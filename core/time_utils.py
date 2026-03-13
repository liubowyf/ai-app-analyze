"""Time-related helpers shared across modules."""

from datetime import datetime, timezone


def utc_now_naive() -> datetime:
    """Return current UTC time without tzinfo for DB compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
