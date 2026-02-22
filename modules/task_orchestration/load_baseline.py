"""Concurrency baseline recommendations for task workers."""

from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional

from core.config import settings


def count_configured_emulators(emulators: Optional[Iterable[str]] = None) -> int:
    """Count valid emulator endpoints like host:port."""
    rows = list(emulators) if emulators is not None else list(settings.android_emulators)
    seen = set()
    count = 0
    for item in rows:
        if not item or ":" not in item:
            continue
        host, port_raw = item.rsplit(":", 1)
        if not host.strip():
            continue
        try:
            int(port_raw)
        except ValueError:
            continue
        key = f"{host.strip()}:{port_raw.strip()}"
        if key in seen:
            continue
        seen.add(key)
        count += 1
    return count


def recommend_worker_baseline(
    emulator_count: int,
    cpu_count: Optional[int] = None,
) -> Dict[str, int]:
    """Compute practical concurrency baselines for current architecture."""
    cpu = cpu_count or os.cpu_count() or 2
    emulator_slots = max(1, int(emulator_count))

    # Dynamic worker should never exceed emulator slots.
    dynamic_concurrency = max(1, min(emulator_slots, cpu))

    # Static/report stages are mostly CPU/IO bound and can run with a small buffer.
    static_concurrency = max(1, min(max(2, dynamic_concurrency), cpu))
    report_concurrency = max(1, min(max(2, dynamic_concurrency), cpu))

    # API workers kept moderate to avoid DB connection burst.
    api_workers = max(1, min(4, max(1, cpu // 2)))

    return {
        "cpu_count": int(cpu),
        "emulator_count": emulator_slots,
        "dynamic_worker_concurrency": dynamic_concurrency,
        "static_worker_concurrency": static_concurrency,
        "report_worker_concurrency": report_concurrency,
        "api_workers": api_workers,
    }


def build_worker_commands(baseline: Dict[str, int]) -> List[str]:
    """Render recommended process commands from baseline values."""
    return [
        "uvicorn api.main:app --host 0.0.0.0 --port 8000 "
        f"--workers {baseline['api_workers']}",
        "celery -A workers.celery_app worker -Q dynamic -l info "
        f"--concurrency={baseline['dynamic_worker_concurrency']} --prefetch-multiplier=1",
        "celery -A workers.celery_app worker -Q static -l info "
        f"--concurrency={baseline['static_worker_concurrency']} --prefetch-multiplier=1",
        "celery -A workers.celery_app worker -Q report -l info "
        f"--concurrency={baseline['report_worker_concurrency']} --prefetch-multiplier=1",
    ]
