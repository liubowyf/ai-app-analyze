"""Runtime config helpers for scheduling gate scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GateRuntimeConfig:
    collect_timeout_seconds: int = 30
    phase5_runs: int = 3
    window_minutes: int = 30
    guard_min_sample: int = 30


def _read_int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except Exception:
        return default
    if value < minimum:
        return default
    return value


def load_gate_runtime_config() -> GateRuntimeConfig:
    return GateRuntimeConfig(
        collect_timeout_seconds=_read_int_env("GATE_COLLECT_TIMEOUT_SECONDS", 30, minimum=1),
        phase5_runs=_read_int_env("GATE_PHASE5_RUNS", 3, minimum=1),
        window_minutes=_read_int_env("GATE_WINDOW_MINUTES", 30, minimum=1),
        guard_min_sample=_read_int_env("GATE_MIN_SAMPLE", 30, minimum=1),
    )
