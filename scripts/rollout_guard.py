"""Rollout guard automation for continue/rollback decisions."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _task_has_zero_evidence(task: dict[str, Any]) -> bool:
    return any(
        _to_int(task.get(field, 0), default=0) <= 0
        for field in ("runs", "network", "domains", "img_count")
    )


def _failure_rate(snapshot: dict[str, Any]) -> float:
    if "failure_rate" in snapshot:
        return max(0.0, _to_float(snapshot.get("failure_rate"), default=0.0))

    success_rate = _to_float(snapshot.get("success_rate"), default=0.0)
    success_rate = min(1.0, max(0.0, success_rate))
    return 1.0 - success_rate


def decide_rollout_action(
    snapshot: dict[str, Any],
    validation_mode: str = "e2e",
    success_rate_threshold: float = 0.95,
    max_stuck_tasks: int = 0,
    min_sample: int = 30,
) -> tuple[str, str]:
    """Return rollout action based on deterministic trigger rules."""
    mode = str(validation_mode or snapshot.get("validation_mode", "e2e")).strip().lower()

    if not _to_bool(snapshot.get("can_enqueue", False)):
        return "rollback_now", "backend_not_ready"

    if mode == "scheduling":
        if not _to_bool(snapshot.get("rollback_ready", False)):
            return "rollback_now", "rollback_not_ready"
        stuck_tasks = _to_int(snapshot.get("stuck_tasks", 0), default=0)
        if stuck_tasks > max(0, max_stuck_tasks):
            return "rollback_now", "scheduling_stuck_tasks_detected"
        total_tasks = _to_int(snapshot.get("total_tasks", 0), default=0)
        if total_tasks < max(0, min_sample):
            return "hold", "insufficient_sample_size"
        success_rate = _to_float(snapshot.get("success_rate", 0.0), default=0.0)
        if success_rate < max(0.0, success_rate_threshold):
            return "rollback_now", "scheduling_success_rate_low"
        return "continue", "all_gates_passed"

    tasks = snapshot.get("tasks") or []
    if isinstance(tasks, list) and any(isinstance(task, dict) and _task_has_zero_evidence(task) for task in tasks):
        return "rollback_now", "zero_evidence_task_detected"

    if _failure_rate(snapshot) > (1.0 - max(0.0, min(1.0, success_rate_threshold))):
        return "rollback_now", "failure_rate_above_5_percent"

    return "continue", "all_gates_passed"


def _read_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    if args.snapshot_json:
        with open(args.snapshot_json, "r", encoding="utf-8") as f:
            return json.load(f)

    env_payload = os.getenv("ROLLOUT_STATS_SNAPSHOT")
    if env_payload:
        return json.loads(env_payload)

    payload = os.sys.stdin.read().strip()
    if payload:
        return json.loads(payload)

    return {}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate rollout guard triggers.")
    parser.add_argument("--snapshot-json", help="Path to rolling stats snapshot JSON")
    parser.add_argument(
        "--validation-mode",
        choices=("scheduling", "e2e"),
        default="e2e",
        help="Guard rule set mode (default: e2e)",
    )
    parser.add_argument(
        "--success-rate-threshold",
        type=float,
        default=0.95,
        help="Minimum acceptable success rate",
    )
    parser.add_argument(
        "--max-stuck-tasks",
        type=int,
        default=0,
        help="Maximum allowed stuck tasks in scheduling mode",
    )
    parser.add_argument(
        "--min-sample",
        type=int,
        default=30,
        help="Minimum sample size before success-rate gate in scheduling mode",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    snapshot = _read_snapshot(args)
    action, reason = decide_rollout_action(
        snapshot,
        validation_mode=args.validation_mode,
        success_rate_threshold=args.success_rate_threshold,
        max_stuck_tasks=args.max_stuck_tasks,
        min_sample=args.min_sample,
    )
    print(f"action={action}")
    print(f"reason={reason}")
    if action == "continue":
        return 0
    if action == "hold":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
