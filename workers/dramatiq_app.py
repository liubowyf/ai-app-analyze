"""Dramatiq application bootstrap (optional until migration cutover)."""

from __future__ import annotations

import logging
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)

dramatiq: Any = None
dramatiq_broker: Any = None

try:
    import dramatiq as _dramatiq
    from dramatiq.brokers.redis import RedisBroker

    dramatiq = _dramatiq

    try:
        dramatiq_broker = RedisBroker(url=settings.REDIS_BROKER_URL)
        dramatiq.set_broker(dramatiq_broker)
    except Exception as exc:
        logger.warning("Failed to initialize Dramatiq Redis broker: %s", exc)
        dramatiq_broker = None
except Exception as exc:
    logger.warning("Dramatiq not available yet: %s", exc)


def is_dramatiq_ready() -> bool:
    """Return whether Dramatiq runtime is importable and initialized."""
    return dramatiq is not None and dramatiq_broker is not None
